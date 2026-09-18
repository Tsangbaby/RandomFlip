#import "TransitionDiagnostics.h"
#import "RandomIconsFlip-Bridging-Header.h"

#import <UIKit/UIKit.h>
#import <UIKit/UIAccessibility.h>
#import <errno.h>
#import <fcntl.h>
#import <objc/runtime.h>
#import <os/lock.h>
#import <stdio.h>
#import <stdlib.h>
#import <string.h>
#import <substrate.h>
#import <sys/stat.h>
#import <sys/sysctl.h>
#import <unistd.h>

static NSString * const RFDiagnosticLogPrefix = @"[RFAppToHomeDiag]";
static NSString * const RFDiagnosticPackageVersion = @"0.0.9~diag2";
static NSString * const RFDiagnosticBaselineVersion = @"0.0.8";
static const char * const RFDiagnosticPackageVersionCString = "0.0.9~diag2";
static const char * const RFDiagnosticStatusPath = "/tmp/com.tsangbaby.randomiconsflip.transitiondiag.status.txt";
static const char * const RFDiagnosticStatusDirectory = "/private/var/tmp";
static const char * const RFDiagnosticStatusFilename = "com.tsangbaby.randomiconsflip.transitiondiag.status.txt";
static const NSUInteger RFMaximumStoredEvents = 128;
static const NSUInteger RFMaximumSerializedBytes = 1024 * 1024;
// Darwin protection class C == complete until first user authentication.
static const int RFProtectionClassC = 3;

static dispatch_queue_t RFDiagnosticWriterQueue;
static dispatch_queue_t RFDiagnosticStatusQueue;
static NSMutableDictionary *RFDiagnosticState;
static os_unfair_lock RFAdmissionLock = OS_UNFAIR_LOCK_INIT;
static BOOL RFDiagnosticsStarted = NO;
static NSUInteger RFEventSequence = 0;
static NSUInteger RFEventsAdmitted = 0;

typedef NS_ENUM(NSUInteger, RFDiagnosticStage) {
	RFDiagnosticStageEntry = 0,
	RFDiagnosticStageOffMain,
	RFDiagnosticStageQueueReady,
	RFDiagnosticStageInventoryReady,
	RFDiagnosticStageHooksReady,
	RFDiagnosticStageStateUnavailable,
	RFDiagnosticStageSerializationFailed,
	RFDiagnosticStagePlistWriteOK,
	RFDiagnosticStagePlistInvalidData,
	RFDiagnosticStagePlistDirectoryPreparationFailed,
	RFDiagnosticStagePlistInvalidPath,
	RFDiagnosticStagePlistDirectoryValidationFailed,
	RFDiagnosticStagePlistFileOpenFailed,
	RFDiagnosticStagePlistFileValidationFailed,
	RFDiagnosticStagePlistProtectionFailed,
	RFDiagnosticStagePlistDataWriteFailed,
	RFDiagnosticStagePlistFinalValidationFailed,
	RFDiagnosticStageWriterException,
	RFDiagnosticStageStartupException,
};

typedef NS_ENUM(NSUInteger, RFDiagnosticWriteResult) {
	RFDiagnosticWriteResultSuccess = 0,
	RFDiagnosticWriteResultInvalidData,
	RFDiagnosticWriteResultDirectoryPreparationFailed,
	RFDiagnosticWriteResultInvalidPath,
	RFDiagnosticWriteResultDirectoryValidationFailed,
	RFDiagnosticWriteResultFileOpenFailed,
	RFDiagnosticWriteResultFileValidationFailed,
	RFDiagnosticWriteResultProtectionFailed,
	RFDiagnosticWriteResultDataWriteFailed,
	RFDiagnosticWriteResultFinalValidationFailed,
};

typedef NS_ENUM(NSUInteger, RFHookReturnKind) {
	RFHookReturnKindUnsupported = 0,
	RFHookReturnKindVoid,
};

static const char *RFSkipDiagnosticTypeQualifiers(const char *type) {
	if (type == NULL) {
		return "";
	}
	while (*type != '\0' && strchr("rnNoORV", *type) != NULL) {
		type++;
	}
	return type;
}

static NSString *RFBoundedString(NSString *value, NSUInteger maximumLength) {
	if (value.length == 0) {
		return @"unknown";
	}
	if (value.length <= maximumLength) {
		return value;
	}
	return [value substringToIndex:maximumLength];
}

NSString *RFTransitionDiagnosticsOutputPath(void) {
	return @"/var/mobile/Library/Preferences/com.tsangbaby.randomiconsflip.transitiondiag.plist";
}

static NSString *RFOSBuild(void) {
	size_t length = 0;
	if (sysctlbyname("kern.osversion", NULL, &length, NULL, 0) != 0 || length == 0) {
		return @"unknown";
	}

	char *buffer = calloc(length, sizeof(char));
	if (buffer == NULL) {
		return @"unknown";
	}

	NSString *build = @"unknown";
	if (sysctlbyname("kern.osversion", buffer, &length, NULL, 0) == 0) {
		NSString *decoded = [NSString stringWithUTF8String:buffer];
		if (decoded.length > 0) {
			build = RFBoundedString(decoded, 64);
		}
	}
	free(buffer);
	return build;
}

static BOOL RFReserveEventSlot(void) {
	BOOL reserved = NO;
	os_unfair_lock_lock(&RFAdmissionLock);
	if (RFEventsAdmitted >= RFMaximumStoredEvents) {
		reserved = NO;
	} else {
		RFEventsAdmitted += 1;
		reserved = YES;
	}
	os_unfair_lock_unlock(&RFAdmissionLock);
	return reserved;
}

static UIWindowScene *RFMainWindowScene(void) {
	UIApplication *application = UIApplication.sharedApplication;
	UIWindowScene *fallback = nil;
	for (UIScene *scene in application.connectedScenes) {
		if (![scene isKindOfClass:UIWindowScene.class]) {
			continue;
		}
		UIWindowScene *windowScene = (UIWindowScene *)scene;
		if (windowScene.screen != UIScreen.mainScreen) {
			continue;
		}
		if (fallback == nil) {
			fallback = windowScene;
		}
		if (windowScene.activationState == UISceneActivationStateForegroundActive ||
			windowScene.activationState == UISceneActivationStateForegroundInactive) {
			return windowScene;
		}
	}
	return fallback;
}

static UIWindow *RFMainWindow(UIWindowScene *windowScene) {
	UIWindow *fallback = nil;
	for (UIWindow *window in windowScene.windows) {
		if (window.screen != UIScreen.mainScreen) {
			continue;
		}
		if (fallback == nil && !window.hidden) {
			fallback = window;
		}
		if (window.isKeyWindow) {
			return window;
		}
	}
	return fallback;
}

static NSDictionary *RFGeometrySnapshot(void) {
	UIScreen *screen = UIScreen.mainScreen;
	UIWindowScene *windowScene = RFMainWindowScene();
	UIWindow *window = RFMainWindow(windowScene);
	UIEdgeInsets safeArea = window != nil ? window.safeAreaInsets : UIEdgeInsetsZero;
	UIInterfaceOrientation sceneOrientation = windowScene != nil ? windowScene.interfaceOrientation : UIInterfaceOrientationUnknown;
	CGRect bounds = screen.bounds;

	return @{
		@"screenWidth": @(CGRectGetWidth(bounds)),
		@"screenHeight": @(CGRectGetHeight(bounds)),
		@"screenScale": @(screen.scale),
		@"safeAreaTop": @(safeArea.top),
		@"safeAreaBottom": @(safeArea.bottom),
		@"sceneInterfaceOrientation": @((NSInteger)sceneOrientation),
	};
}

static id RFTransitionContextForObject(id object) {
	for (NSString *selectorName in @[@"_transitionContext", @"transitionContext"]) {
		id context = RFInvokeObjectSelector(object, selectorName);
		if (context != nil) {
			return context;
		}
	}
	return nil;
}

static NSNumber *RFInterfaceOrientationForContext(id context, NSString **sourceSelector) {
	for (NSString *selectorName in @[
		@"interfaceOrientationOrPreferredOrientation",
		@"interfaceOrientation",
		@"preferredInterfaceOrientation",
	]) {
		NSNumber *orientation = RFReadIntegerSelector(context, selectorName);
		if (orientation != nil) {
			if (sourceSelector != NULL) {
				*sourceSelector = selectorName;
			}
			return orientation;
		}
	}
	return nil;
}

static BOOL RFPrepareOutputDirectory(NSString *directory) {
	NSError *directoryError = nil;
	BOOL created = [[NSFileManager defaultManager] createDirectoryAtPath:directory
		withIntermediateDirectories:YES
		attributes:@{NSFilePosixPermissions: @0700}
		error:&directoryError];
	if (!created || directoryError != nil) {
		return NO;
	}

	struct stat directoryStatus;
	if (lstat(directory.fileSystemRepresentation, &directoryStatus) != 0) {
		return NO;
	}
	return S_ISDIR(directoryStatus.st_mode) && directoryStatus.st_uid == geteuid();
}

static BOOL RFWriteAllBytes(int fileDescriptor, const uint8_t *bytes, NSUInteger length) {
	NSUInteger totalWritten = 0;
	while (totalWritten < length) {
		ssize_t result = write(fileDescriptor, bytes + totalWritten, length - totalWritten);
		if (result < 0 && errno == EINTR) {
			continue;
		}
		if (result <= 0) {
			return NO;
		}
		totalWritten += (NSUInteger)result;
	}
	return YES;
}

static BOOL RFSameInode(struct stat left, struct stat right) {
	return left.st_dev == right.st_dev && left.st_ino == right.st_ino;
}

static const char *RFDiagnosticStageName(RFDiagnosticStage stage) {
	switch (stage) {
		case RFDiagnosticStageEntry: return "entry";
		case RFDiagnosticStageOffMain: return "off-main";
		case RFDiagnosticStageQueueReady: return "queue-ready";
		case RFDiagnosticStageInventoryReady: return "inventory-ready";
		case RFDiagnosticStageHooksReady: return "hooks-ready";
		case RFDiagnosticStageStateUnavailable: return "state-unavailable";
		case RFDiagnosticStageSerializationFailed: return "serialization-failed";
		case RFDiagnosticStagePlistWriteOK: return "plist-write-ok";
		case RFDiagnosticStagePlistInvalidData: return "plist-invalid-data";
		case RFDiagnosticStagePlistDirectoryPreparationFailed: return "plist-directory-prepare-failed";
		case RFDiagnosticStagePlistInvalidPath: return "plist-invalid-path";
		case RFDiagnosticStagePlistDirectoryValidationFailed: return "plist-directory-validation-failed";
		case RFDiagnosticStagePlistFileOpenFailed: return "plist-file-open-failed";
		case RFDiagnosticStagePlistFileValidationFailed: return "plist-file-validation-failed";
		case RFDiagnosticStagePlistProtectionFailed: return "plist-protection-failed";
		case RFDiagnosticStagePlistDataWriteFailed: return "plist-data-write-failed";
		case RFDiagnosticStagePlistFinalValidationFailed: return "plist-final-validation-failed";
		case RFDiagnosticStageWriterException: return "writer-exception";
		case RFDiagnosticStageStartupException: return "startup-exception";
	}
	return "invalid-stage";
}

static RFDiagnosticStage RFDiagnosticStageForWriteResult(RFDiagnosticWriteResult result) {
	switch (result) {
		case RFDiagnosticWriteResultSuccess: return RFDiagnosticStagePlistWriteOK;
		case RFDiagnosticWriteResultInvalidData: return RFDiagnosticStagePlistInvalidData;
		case RFDiagnosticWriteResultDirectoryPreparationFailed: return RFDiagnosticStagePlistDirectoryPreparationFailed;
		case RFDiagnosticWriteResultInvalidPath: return RFDiagnosticStagePlistInvalidPath;
		case RFDiagnosticWriteResultDirectoryValidationFailed: return RFDiagnosticStagePlistDirectoryValidationFailed;
		case RFDiagnosticWriteResultFileOpenFailed: return RFDiagnosticStagePlistFileOpenFailed;
		case RFDiagnosticWriteResultFileValidationFailed: return RFDiagnosticStagePlistFileValidationFailed;
		case RFDiagnosticWriteResultProtectionFailed: return RFDiagnosticStagePlistProtectionFailed;
		case RFDiagnosticWriteResultDataWriteFailed: return RFDiagnosticStagePlistDataWriteFailed;
		case RFDiagnosticWriteResultFinalValidationFailed: return RFDiagnosticStagePlistFinalValidationFailed;
	}
	return RFDiagnosticStagePlistFinalValidationFailed;
}

static BOOL RFWriteDiagnosticStatus(RFDiagnosticStage stage) {
	const char *stageName = RFDiagnosticStageName(stage);
	char payload[192] = {0};
	int payloadLength = snprintf(
		payload,
		sizeof(payload),
		"schema=1\nversion=%s\nstage=%s\n",
		RFDiagnosticPackageVersionCString,
		stageName
	);
	if (payloadLength <= 0 || (size_t)payloadLength >= sizeof(payload)) {
		return NO;
	}

	int directoryDescriptor = -1;
	int fileDescriptor = -1;
	BOOL outputCreated = NO;
	BOOL openedStatusValid = NO;
	BOOL outputValidated = NO;
	BOOL success = NO;
	struct stat directoryStatus = {0};
	struct stat openedStatus = {0};
	struct stat finalEntryStatus = {0};

	directoryDescriptor = open(
		RFDiagnosticStatusDirectory,
		O_RDONLY | O_DIRECTORY | O_NOFOLLOW | O_CLOEXEC | O_NONBLOCK
	);
	if (directoryDescriptor < 0 ||
		fstat(directoryDescriptor, &directoryStatus) != 0 ||
		!S_ISDIR(directoryStatus.st_mode)) {
		goto cleanup;
	}
	BOOL rootOwnedStickyDirectory = directoryStatus.st_uid == 0 &&
		(directoryStatus.st_mode & S_ISVTX) != 0;
	BOOL privateUserDirectory = directoryStatus.st_uid == geteuid() &&
		(directoryStatus.st_mode & (S_IWGRP | S_IWOTH)) == 0;
	if (!rootOwnedStickyDirectory && !privateUserDirectory) {
		goto cleanup;
	}

	fileDescriptor = openat(
		directoryDescriptor,
		RFDiagnosticStatusFilename,
		O_WRONLY | O_CREAT | O_EXCL | O_NOFOLLOW | O_CLOEXEC | O_NONBLOCK,
		S_IRUSR | S_IWUSR
	);
	if (fileDescriptor >= 0) {
		outputCreated = YES;
	} else if (errno == EEXIST) {
		fileDescriptor = openat(
			directoryDescriptor,
			RFDiagnosticStatusFilename,
			O_WRONLY | O_NOFOLLOW | O_CLOEXEC | O_NONBLOCK
		);
	}
	if (fileDescriptor < 0 || fstat(fileDescriptor, &openedStatus) != 0) {
		goto cleanup;
	}
	openedStatusValid = YES;

	if (!S_ISREG(openedStatus.st_mode) ||
		openedStatus.st_uid != geteuid() ||
		openedStatus.st_nlink != 1 ||
		fchmod(fileDescriptor, S_IRUSR | S_IWUSR) != 0) {
		goto cleanup;
	}
	outputValidated = YES;

	if (ftruncate(fileDescriptor, 0) != 0 ||
		!RFWriteAllBytes(fileDescriptor, (const uint8_t *)payload, (NSUInteger)payloadLength)) {
		goto cleanup;
	}

	if (fstat(fileDescriptor, &openedStatus) != 0 ||
		!S_ISREG(openedStatus.st_mode) ||
		openedStatus.st_uid != geteuid() ||
		openedStatus.st_nlink != 1 ||
		(openedStatus.st_mode & 0777) != 0600 ||
		fstatat(directoryDescriptor, RFDiagnosticStatusFilename, &finalEntryStatus, AT_SYMLINK_NOFOLLOW) != 0 ||
		!S_ISREG(finalEntryStatus.st_mode) ||
		finalEntryStatus.st_uid != geteuid() ||
		finalEntryStatus.st_nlink != 1 ||
		!RFSameInode(openedStatus, finalEntryStatus)) {
		goto cleanup;
	}

	success = YES;

cleanup:
	if (!success && directoryDescriptor >= 0 && openedStatusValid && (outputCreated || outputValidated)) {
		struct stat cleanupStatus = {0};
		if (fstatat(directoryDescriptor, RFDiagnosticStatusFilename, &cleanupStatus, AT_SYMLINK_NOFOLLOW) == 0 &&
			RFSameInode(openedStatus, cleanupStatus)) {
			unlinkat(directoryDescriptor, RFDiagnosticStatusFilename, 0);
		}
	}
	if (fileDescriptor >= 0) {
		close(fileDescriptor);
	}
	if (directoryDescriptor >= 0) {
		close(directoryDescriptor);
	}
	return success;
}

static void RFEnqueueDiagnosticStatus(RFDiagnosticStage stage) {
	dispatch_queue_t statusQueue = RFDiagnosticStatusQueue;
	if (statusQueue == nil) {
		return;
	}
	dispatch_async(RFDiagnosticStatusQueue, ^{
		@autoreleasepool {
			RFWriteDiagnosticStatus(stage);
		}
	});
}

static RFDiagnosticWriteResult RFSecurelyWriteData(NSData *data) {
	NSUInteger dataLength = data.length;
	const uint8_t *bytes = data.bytes;
	if (dataLength == 0 || dataLength > RFMaximumSerializedBytes || bytes == NULL) {
		return RFDiagnosticWriteResultInvalidData;
	}

	NSString *outputPath = RFTransitionDiagnosticsOutputPath();
	NSString *directory = outputPath.stringByDeletingLastPathComponent;
	if (!RFPrepareOutputDirectory(directory)) {
		return RFDiagnosticWriteResultDirectoryPreparationFailed;
	}

	NSString *outputName = outputPath.lastPathComponent;
	const char *directoryPath = directory.fileSystemRepresentation;
	const char *outputFileName = outputName.fileSystemRepresentation;
	if (directoryPath == NULL || outputFileName == NULL) {
		return RFDiagnosticWriteResultInvalidPath;
	}

	int directoryDescriptor = -1;
	int fileDescriptor = -1;
	BOOL outputCreated = NO;
	BOOL openedStatusValid = NO;
	BOOL outputValidated = NO;
	RFDiagnosticWriteResult result = RFDiagnosticWriteResultDirectoryValidationFailed;
	struct stat directoryStatus = {0};
	struct stat openedStatus = {0};
	struct stat finalEntryStatus = {0};

	directoryDescriptor = open(directoryPath, O_RDONLY | O_DIRECTORY | O_NOFOLLOW | O_CLOEXEC);
	if (directoryDescriptor < 0 ||
		fstat(directoryDescriptor, &directoryStatus) != 0 ||
		!S_ISDIR(directoryStatus.st_mode) ||
		directoryStatus.st_uid != geteuid() ||
		(directoryStatus.st_mode & (S_IWGRP | S_IWOTH)) != 0) {
		goto cleanup;
	}

	result = RFDiagnosticWriteResultFileOpenFailed;
	fileDescriptor = openat(
		directoryDescriptor,
		outputFileName,
		O_WRONLY | O_CREAT | O_EXCL | O_NOFOLLOW | O_CLOEXEC | O_NONBLOCK,
		S_IRUSR | S_IWUSR
	);
	if (fileDescriptor >= 0) {
		outputCreated = YES;
	} else if (errno == EEXIST) {
		fileDescriptor = openat(
			directoryDescriptor,
			outputFileName,
			O_WRONLY | O_NOFOLLOW | O_CLOEXEC | O_NONBLOCK
		);
	}
	if (fileDescriptor < 0 || fstat(fileDescriptor, &openedStatus) != 0) {
		goto cleanup;
	}
	openedStatusValid = YES;

	result = RFDiagnosticWriteResultFileValidationFailed;
	if (!S_ISREG(openedStatus.st_mode) ||
		openedStatus.st_uid != geteuid() ||
		openedStatus.st_nlink != 1 ||
		fchmod(fileDescriptor, S_IRUSR | S_IWUSR) != 0) {
		goto cleanup;
	}
	outputValidated = YES;

	result = RFDiagnosticWriteResultProtectionFailed;
	if (fcntl(fileDescriptor, F_SETPROTECTIONCLASS, RFProtectionClassC) != 0 ||
		fcntl(fileDescriptor, F_GETPROTECTIONCLASS) != RFProtectionClassC) {
		goto cleanup;
	}

	result = RFDiagnosticWriteResultDataWriteFailed;
	if (ftruncate(fileDescriptor, 0) != 0 ||
		!RFWriteAllBytes(fileDescriptor, bytes, dataLength) ||
		fsync(fileDescriptor) != 0) {
		goto cleanup;
	}

	result = RFDiagnosticWriteResultFinalValidationFailed;
	if (fstat(fileDescriptor, &openedStatus) != 0 ||
		!S_ISREG(openedStatus.st_mode) ||
		openedStatus.st_uid != geteuid() ||
		openedStatus.st_nlink != 1 ||
		(openedStatus.st_mode & 0777) != 0600 ||
		fcntl(fileDescriptor, F_GETPROTECTIONCLASS) != RFProtectionClassC ||
		fstatat(directoryDescriptor, outputFileName, &finalEntryStatus, AT_SYMLINK_NOFOLLOW) != 0 ||
		!S_ISREG(finalEntryStatus.st_mode) ||
		finalEntryStatus.st_uid != geteuid() ||
		finalEntryStatus.st_nlink != 1 ||
		!RFSameInode(openedStatus, finalEntryStatus)) {
		goto cleanup;
	}

	result = RFDiagnosticWriteResultSuccess;

cleanup:
	if (result != RFDiagnosticWriteResultSuccess && directoryDescriptor >= 0 && openedStatusValid && (outputCreated || outputValidated)) {
		struct stat cleanupStatus = {0};
		if (fstatat(directoryDescriptor, outputFileName, &cleanupStatus, AT_SYMLINK_NOFOLLOW) == 0 &&
			RFSameInode(openedStatus, cleanupStatus)) {
			unlinkat(directoryDescriptor, outputFileName, 0);
		}
	}
	if (fileDescriptor >= 0) {
		close(fileDescriptor);
	}
	if (directoryDescriptor >= 0) {
		close(directoryDescriptor);
	}
	return result;
}

static void RFWriteStateLocked(void) {
	if (RFDiagnosticState == nil) {
		RFEnqueueDiagnosticStatus(RFDiagnosticStageStateUnavailable);
		return;
	}

	NSError *serializationError = nil;
	NSData *data = [NSPropertyListSerialization dataWithPropertyList:RFDiagnosticState
		format:NSPropertyListXMLFormat_v1_0
		options:0
		error:&serializationError];
	if (data == nil || serializationError != nil) {
		RFEnqueueDiagnosticStatus(RFDiagnosticStageSerializationFailed);
		NSLog(@"%@ plist serialization failed", RFDiagnosticLogPrefix);
		return;
	}

	RFDiagnosticWriteResult result = RFSecurelyWriteData(data);
	RFEnqueueDiagnosticStatus(RFDiagnosticStageForWriteResult(result));
	if (result != RFDiagnosticWriteResultSuccess) {
		NSLog(@"%@ private plist write failed", RFDiagnosticLogPrefix);
	}
}

static void RFEnqueueEvent(NSDictionary *event) {
	if (RFDiagnosticWriterQueue == nil || event == nil) {
		return;
	}
	NSDictionary *immutableEvent = [event copy];
	dispatch_async(RFDiagnosticWriterQueue, ^{
		@autoreleasepool {
			@try {
				if (RFDiagnosticState == nil) {
					return;
				}

				RFEventSequence += 1;
				NSMutableDictionary *storedEvent = [immutableEvent mutableCopy];
				storedEvent[@"sequence"] = @(RFEventSequence);

				NSMutableArray *events = [RFDiagnosticState[@"events"] mutableCopy] ?: [NSMutableArray array];
				[events addObject:storedEvent];
				if (events.count > RFMaximumStoredEvents) {
					NSRange overflow = NSMakeRange(0, events.count - RFMaximumStoredEvents);
					[events removeObjectsInRange:overflow];
				}
				RFDiagnosticState[@"events"] = events;
				RFDiagnosticState[@"lastEvent"] = storedEvent;

				NSString *eventName = storedEvent[@"event"] ?: @"unknown";
				NSMutableDictionary *counters = [RFDiagnosticState[@"counters"] mutableCopy] ?: [NSMutableDictionary dictionary];
				NSUInteger count = [counters[eventName] unsignedIntegerValue];
				counters[eventName] = @(count + 1);
				RFDiagnosticState[@"counters"] = counters;
				RFWriteStateLocked();
			} @catch (__unused NSException *exception) {
				RFEnqueueDiagnosticStatus(RFDiagnosticStageWriterException);
				NSLog(@"%@ writerException", RFDiagnosticLogPrefix);
			}
		}
	});
}

static NSDictionary *RFBuildLifecycleEvent(id object, SEL selector, NSString *eventName) {
	BOOL mainThread = NSThread.isMainThread;
	NSMutableDictionary *event = [NSMutableDictionary dictionaryWithDictionary:@{
		@"event": RFBoundedString(eventName, 80),
		@"class": RFBoundedString(object != nil ? NSStringFromClass([object class]) : @"unknown", 160),
		@"selector": RFBoundedString(selector != NULL ? NSStringFromSelector(selector) : @"unknown", 160),
		@"captureThreadMain": @(mainThread),
	}];

	if (!mainThread) {
		event[@"mainThreadOnlyFieldsUnavailable"] = @YES;
		return event;
	}

	[event addEntriesFromDictionary:RFGeometrySnapshot()];
	event[@"reduceMotion"] = @(UIAccessibilityIsReduceMotionEnabled());

	NSNumber *goingToLauncher = RFReadBoolSelector(object, @"isGoingToLauncher");
	if (goingToLauncher != nil) {
		event[@"isGoingToLauncher"] = goingToLauncher;
	}
	NSNumber *cancelled = RFReadBoolSelector(object, @"_transitionWasCancelled");
	if (cancelled != nil) {
		event[@"transitionWasCancelled"] = cancelled;
	}

	id context = RFTransitionContextForObject(object);
	NSNumber *contextOrientation = nil;
	BOOL contextOrientationKnown = NO;
	if (context != nil) {
		event[@"transitionContextClass"] = RFBoundedString(NSStringFromClass([context class]), 160);
		NSString *orientationSource = nil;
		contextOrientation = RFInterfaceOrientationForContext(context, &orientationSource);
		if (contextOrientation != nil) {
			event[@"contextInterfaceOrientation"] = contextOrientation;
			event[@"contextOrientationSelector"] = RFBoundedString(orientationSource, 80);
			NSInteger contextOrientationValue = contextOrientation.integerValue;
			contextOrientationKnown = contextOrientationValue != UIInterfaceOrientationUnknown;
		}
	}
	event[@"contextOrientationKnown"] = @(contextOrientationKnown);

	NSInteger effectiveOrientation = [event[@"sceneInterfaceOrientation"] integerValue];
	NSString *effectiveOrientationSource = @"scene";
	if (contextOrientationKnown) {
		effectiveOrientation = contextOrientation.integerValue;
		effectiveOrientationSource = @"context";
	}
	event[@"effectiveInterfaceOrientation"] = @(effectiveOrientation);
	event[@"effectiveOrientationSource"] = effectiveOrientationSource;
	event[@"portrait"] = @(UIInterfaceOrientationIsPortrait((UIInterfaceOrientation)effectiveOrientation));
	return event;
}

static void RFSafelyRecordLifecycleEvent(id object, SEL selector, NSString *eventName) {
	if (!RFReserveEventSlot()) {
		return;
	}
	@try {
		RFEnqueueEvent(RFBuildLifecycleEvent(object, selector, eventName));
	} @catch (__unused NSException *exception) {
		// Diagnostic capture must never prevent the original lifecycle method.
	}
}

static RFHookReturnKind RFZeroArgumentReturnKind(Method method, NSString **encodingOut) {
	const char *rawEncoding = method != NULL ? method_getTypeEncoding(method) : NULL;
	if (encodingOut != NULL) {
		NSString *encoding = rawEncoding != NULL ? [NSString stringWithUTF8String:rawEncoding] : @"<missing>";
		*encodingOut = RFBoundedString(encoding, 256);
	}
	if (rawEncoding == NULL) {
		return RFHookReturnKindUnsupported;
	}

	NSMethodSignature *signature = [NSMethodSignature signatureWithObjCTypes:rawEncoding];
	if (signature == nil || signature.numberOfArguments != 2) {
		return RFHookReturnKindUnsupported;
	}

	const char *selfType = RFSkipDiagnosticTypeQualifiers([signature getArgumentTypeAtIndex:0]);
	const char *selectorType = RFSkipDiagnosticTypeQualifiers([signature getArgumentTypeAtIndex:1]);
	if (selfType[0] != '@' || selectorType[0] != ':') {
		return RFHookReturnKindUnsupported;
	}

	const char *returnType = RFSkipDiagnosticTypeQualifiers(signature.methodReturnType);
	if (returnType[0] == 'v') {
		return RFHookReturnKindVoid;
	}
	return RFHookReturnKindUnsupported;
}

#define RF_DEFINE_VOID_LIFECYCLE_HOOK(NAME, EVENT_NAME) \
	static IMP NAME##OriginalIMP = NULL; \
	static void NAME##Replacement(id object, SEL selector) { \
		IMP originalIMP = NAME##OriginalIMP; \
		if (originalIMP == NULL) { \
			return; \
		} \
		RFSafelyRecordLifecycleEvent(object, selector, EVENT_NAME); \
		((void (*)(id, SEL))originalIMP)(object, selector); \
	}

RF_DEFINE_VOID_LIFECYCLE_HOOK(RFTransactionBeginHook, @"transaction.begin")
RF_DEFINE_VOID_LIFECYCLE_HOOK(RFTransactionFinishHook, @"transaction.finish")
RF_DEFINE_VOID_LIFECYCLE_HOOK(RFIconZoomBeginHook, @"modifier.begin")
RF_DEFINE_VOID_LIFECYCLE_HOOK(RFIconZoomEndHook, @"modifier.end")
RF_DEFINE_VOID_LIFECYCLE_HOOK(RFCenterZoomBeginHook, @"modifier.begin")
RF_DEFINE_VOID_LIFECYCLE_HOOK(RFCenterZoomEndHook, @"modifier.end")
RF_DEFINE_VOID_LIFECYCLE_HOOK(RFHomeGestureBeginHook, @"modifier.begin")
RF_DEFINE_VOID_LIFECYCLE_HOOK(RFHomeGestureEndHook, @"modifier.end")
RF_DEFINE_VOID_LIFECYCLE_HOOK(RFFinalDestinationBeginHook, @"modifier.begin")
RF_DEFINE_VOID_LIFECYCLE_HOOK(RFFinalDestinationEndHook, @"modifier.end")
RF_DEFINE_VOID_LIFECYCLE_HOOK(RFSystemApertureBeginHook, @"modifier.begin")
RF_DEFINE_VOID_LIFECYCLE_HOOK(RFSystemApertureEndHook, @"modifier.end")

#undef RF_DEFINE_VOID_LIFECYCLE_HOOK

typedef struct {
	const char *className;
	const char *selectorName;
	IMP replacementIMP;
	IMP *originalSlot;
} RFHookSpecification;

static NSDictionary *RFInstallZeroArgumentLifecycleHook(
	NSString *className,
	NSString *selectorName,
	IMP replacementIMP,
	IMP *originalSlot
) {
	Class targetClass = NSClassFromString(className);
	if (targetClass == Nil) {
		return @{ @"status": @"missingClass" };
	}

	SEL selector = NSSelectorFromString(selectorName);
	Method method = class_getInstanceMethod(targetClass, selector);
	if (method == NULL) {
		return @{ @"status": @"missingSelector" };
	}

	NSString *encoding = nil;
	RFHookReturnKind returnKind = RFZeroArgumentReturnKind(method, &encoding);
	if (returnKind == RFHookReturnKindUnsupported) {
		return @{
			@"status": @"unsupportedSignature",
			@"typeEncoding": encoding ?: @"<missing>",
		};
	}

	if (replacementIMP == NULL || originalSlot == NULL) {
		return @{
			@"status": @"missingImplementation",
			@"typeEncoding": encoding ?: @"<missing>",
		};
	}

	*originalSlot = NULL;
	MSHookMessageEx(targetClass, selector, replacementIMP, originalSlot);
	BOOL predecessorReady = (*originalSlot != NULL);

	return @{
		@"status": predecessorReady ? @"installed" : @"predecessorUnavailable",
		@"typeEncoding": encoding ?: @"<missing>",
		@"returnKind": @"void",
	};
}

static NSArray<NSDictionary *> *RFClassInventorySpecifications(void) {
	return @[
		@{
			@"class": @"SBToAppsWorkspaceTransaction",
			@"selectors": @[
				@"isGoingToLauncher", @"_transitionWasCancelled", @"_transitionContext",
				@"_beginAnimation", @"_animationDidFinish",
			],
		},
		@{
			@"class": @"SBWorkspaceApplicationSceneTransitionContext",
			@"selectors": @[
				@"interfaceOrientation", @"preferredInterfaceOrientation",
				@"interfaceOrientationOrPreferredOrientation", @"activatingEntity",
				@"deactivatingEntity",
			],
		},
		@{
			@"class": @"SBFullScreenToHomeIconZoomSwitcherModifier",
			@"selectors": @[
				@"transitionWillBegin", @"transitionDidEnd", @"frameForIndex:",
				@"scaleForIndex:", @"cornerRadiiForIndex:", @"layoutSettingsForTargetCenter:",
			],
		},
		@{
			@"class": @"SBFullScreenToHomeCenterZoomDownSwitcherModifier",
			@"selectors": @[@"transitionWillBegin", @"transitionDidEnd", @"frameForIndex:"],
		},
		@{
			@"class": @"SBHomeGestureToHomeSwitcherModifier",
			@"selectors": @[@"transitionWillBegin", @"transitionDidEnd"],
		},
		@{
			@"class": @"SBHomeGestureFinalDestinationSwitcherModifier",
			@"selectors": @[@"currentFinalDestination", @"handleGestureEvent:"],
		},
		@{
			@"class": @"SBFullScreenToHomeSystemApertureSwitcherModifier",
			@"selectors": @[@"transitionWillBegin", @"transitionDidEnd", @"frameForIndex:"],
		},
		@{
			@"class": @"SBFluidSwitcherAnimationController",
			@"selectors": @[@"_beginAnimation", @"_animationDidFinish"],
		},
	];
}

static NSDictionary *RFBuildClassInventory(void) {
	NSMutableDictionary *inventory = [NSMutableDictionary dictionary];
	for (NSDictionary *specification in RFClassInventorySpecifications()) {
		NSString *className = specification[@"class"];
		Class targetClass = NSClassFromString(className);
		NSMutableDictionary *methods = [NSMutableDictionary dictionary];
		for (NSString *selectorName in specification[@"selectors"]) {
			Method method = targetClass != Nil
				? class_getInstanceMethod(targetClass, NSSelectorFromString(selectorName))
				: NULL;
			const char *rawEncoding = method != NULL ? method_getTypeEncoding(method) : NULL;
			NSString *encoding = rawEncoding != NULL ? [NSString stringWithUTF8String:rawEncoding] : @"<missing>";
			methods[selectorName] = RFBoundedString(encoding, 256);
		}
		inventory[className] = @{
			@"present": @(targetClass != Nil),
			@"methods": methods,
		};
	}
	return inventory;
}

static const RFHookSpecification RFHookSpecifications[] = {
	{ "SBToAppsWorkspaceTransaction", "_beginAnimation", (IMP)RFTransactionBeginHookReplacement, &RFTransactionBeginHookOriginalIMP },
	{ "SBToAppsWorkspaceTransaction", "_animationDidFinish", (IMP)RFTransactionFinishHookReplacement, &RFTransactionFinishHookOriginalIMP },
	{ "SBFullScreenToHomeIconZoomSwitcherModifier", "transitionWillBegin", (IMP)RFIconZoomBeginHookReplacement, &RFIconZoomBeginHookOriginalIMP },
	{ "SBFullScreenToHomeIconZoomSwitcherModifier", "transitionDidEnd", (IMP)RFIconZoomEndHookReplacement, &RFIconZoomEndHookOriginalIMP },
	{ "SBFullScreenToHomeCenterZoomDownSwitcherModifier", "transitionWillBegin", (IMP)RFCenterZoomBeginHookReplacement, &RFCenterZoomBeginHookOriginalIMP },
	{ "SBFullScreenToHomeCenterZoomDownSwitcherModifier", "transitionDidEnd", (IMP)RFCenterZoomEndHookReplacement, &RFCenterZoomEndHookOriginalIMP },
	{ "SBHomeGestureToHomeSwitcherModifier", "transitionWillBegin", (IMP)RFHomeGestureBeginHookReplacement, &RFHomeGestureBeginHookOriginalIMP },
	{ "SBHomeGestureToHomeSwitcherModifier", "transitionDidEnd", (IMP)RFHomeGestureEndHookReplacement, &RFHomeGestureEndHookOriginalIMP },
	{ "SBHomeGestureFinalDestinationSwitcherModifier", "transitionWillBegin", (IMP)RFFinalDestinationBeginHookReplacement, &RFFinalDestinationBeginHookOriginalIMP },
	{ "SBHomeGestureFinalDestinationSwitcherModifier", "transitionDidEnd", (IMP)RFFinalDestinationEndHookReplacement, &RFFinalDestinationEndHookOriginalIMP },
	{ "SBFullScreenToHomeSystemApertureSwitcherModifier", "transitionWillBegin", (IMP)RFSystemApertureBeginHookReplacement, &RFSystemApertureBeginHookOriginalIMP },
	{ "SBFullScreenToHomeSystemApertureSwitcherModifier", "transitionDidEnd", (IMP)RFSystemApertureEndHookReplacement, &RFSystemApertureEndHookOriginalIMP },
};

static NSDictionary *RFInstallLifecycleHooks(void) {
	NSMutableDictionary *statuses = [NSMutableDictionary dictionary];
	NSUInteger hookCount = sizeof(RFHookSpecifications) / sizeof(RFHookSpecifications[0]);
	for (NSUInteger index = 0; index < hookCount; index++) {
		const RFHookSpecification *specification = &RFHookSpecifications[index];
		NSString *className = [NSString stringWithUTF8String:specification->className];
		NSString *selectorName = [NSString stringWithUTF8String:specification->selectorName];
		NSString *key = [NSString stringWithFormat:@"%@.%@", className, selectorName];
		@try {
			statuses[key] = RFInstallZeroArgumentLifecycleHook(
				className,
				selectorName,
				specification->replacementIMP,
				specification->originalSlot
			);
		} @catch (__unused NSException *exception) {
			statuses[key] = @{ @"status": @"installationException" };
		}
	}
	return statuses;
}

static NSDictionary *RFInitialDiagnosticState(NSDictionary *inventory) {
	return @{
		@"schemaVersion": @2,
		@"packageVersion": RFDiagnosticPackageVersion,
		@"baselineVersion": RFDiagnosticBaselineVersion,
		@"sessionID": NSUUID.UUID.UUIDString,
		@"osVersion": RFBoundedString(UIDevice.currentDevice.systemVersion, 64),
		@"osBuild": RFOSBuild(),
		@"maximumStoredEvents": @(RFMaximumStoredEvents),
		@"inventory": inventory ?: @{},
		@"hooks": @{},
		@"events": @[],
		@"counters": @{},
		@"privacy": @{
			@"storesAppIdentity": @NO,
			@"storesUserInput": @NO,
			@"storesTouchTrajectory": @NO,
			@"storesAppImages": @NO,
		},
	};
}

void RFTransitionDiagnosticsStart(void) {
	@try {
		if (RFDiagnosticStatusQueue == nil) {
			RFDiagnosticStatusQueue = dispatch_queue_create(
				"com.tsangbaby.randomiconsflip.transitiondiag.status",
				DISPATCH_QUEUE_SERIAL
			);
		}
		if (RFDiagnosticStatusQueue == nil) {
			NSLog(@"%@ status queue unavailable", RFDiagnosticLogPrefix);
			return;
		}
		if (!NSThread.isMainThread) {
			RFEnqueueDiagnosticStatus(RFDiagnosticStageOffMain);
			NSLog(@"%@ startup skipped off main thread", RFDiagnosticLogPrefix);
			return;
		}
		if (RFDiagnosticsStarted) {
			return;
		}
		RFDiagnosticsStarted = YES;
		RFEnqueueDiagnosticStatus(RFDiagnosticStageEntry);

		RFDiagnosticWriterQueue = dispatch_queue_create("com.tsangbaby.randomiconsflip.transitiondiag.writer", DISPATCH_QUEUE_SERIAL);
		if (RFDiagnosticWriterQueue == nil) {
			RFEnqueueDiagnosticStatus(RFDiagnosticStageStartupException);
			return;
		}
		RFEnqueueDiagnosticStatus(RFDiagnosticStageQueueReady);

		NSDictionary *inventory = RFBuildClassInventory();
		RFEnqueueDiagnosticStatus(RFDiagnosticStageInventoryReady);
		NSMutableDictionary *initialState = [RFInitialDiagnosticState(inventory) mutableCopy];
		dispatch_sync(RFDiagnosticWriterQueue, ^{
			RFDiagnosticState = initialState;
		});

		NSDictionary *hookStatuses = RFInstallLifecycleHooks();
		RFEnqueueDiagnosticStatus(RFDiagnosticStageHooksReady);
		dispatch_async(RFDiagnosticWriterQueue, ^{
			@autoreleasepool {
				@try {
					RFDiagnosticState[@"hooks"] = hookStatuses;
					RFWriteStateLocked();
				} @catch (__unused NSException *exception) {
					RFEnqueueDiagnosticStatus(RFDiagnosticStageWriterException);
					NSLog(@"%@ writerException", RFDiagnosticLogPrefix);
				}
			}
		});
		NSLog(
			@"%@ started version=%@ output=%@ status=%s",
			RFDiagnosticLogPrefix,
			RFDiagnosticPackageVersion,
			RFTransitionDiagnosticsOutputPath(),
			RFDiagnosticStatusPath
		);
	} @catch (__unused NSException *exception) {
		RFEnqueueDiagnosticStatus(RFDiagnosticStageStartupException);
		NSLog(@"%@ startupException", RFDiagnosticLogPrefix);
	}
}
