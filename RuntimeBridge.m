#import "RandomIconsFlip-Bridging-Header.h"
#import <objc/message.h>
#import <objc/runtime.h>
#import <string.h>

static const char *RFSkipTypeQualifiers(const char *type) {
	if (type == NULL) {
		return "";
	}

	while (*type != '\0' && strchr("rnNoORV", *type) != NULL) {
		type++;
	}
	return type;
}

static NSMethodSignature *RFZeroArgumentMethodSignature(id object, SEL selector) {
	if (object == nil || selector == NULL || ![object respondsToSelector:selector]) {
		return nil;
	}

	NSMethodSignature *signature = [object methodSignatureForSelector:selector];
	if (signature == nil || signature.numberOfArguments != 2) {
		return nil;
	}
	return signature;
}

NSNumber *RFReadBoolSelector(id object, NSString *selectorName) {
	if (selectorName.length == 0) {
		return nil;
	}

	SEL selector = NSSelectorFromString(selectorName);
	NSMethodSignature *signature = RFZeroArgumentMethodSignature(object, selector);
	if (signature == nil) {
		return nil;
	}

	const char *returnType = RFSkipTypeQualifiers(signature.methodReturnType);
	const char boolEncoding = @encode(BOOL)[0];
	if (returnType[0] != boolEncoding && returnType[0] != 'c') {
		return nil;
	}

	BOOL (*sendBool)(id, SEL) = (BOOL (*)(id, SEL))objc_msgSend;
	return @(sendBool(object, selector));
}

id RFInvokeObjectSelector(id object, NSString *selectorName) {
	if (selectorName.length == 0) {
		return nil;
	}

	SEL selector = NSSelectorFromString(selectorName);
	NSMethodSignature *signature = RFZeroArgumentMethodSignature(object, selector);
	if (signature == nil) {
		return nil;
	}

	const char *returnType = RFSkipTypeQualifiers(signature.methodReturnType);
	if (returnType[0] != '@' && returnType[0] != '#') {
		return nil;
	}

	id (*sendObject)(id, SEL) = (id (*)(id, SEL))objc_msgSend;
	return sendObject(object, selector);
}

id RFSharedInstanceForClassNamed(NSString *className) {
	Class targetClass = NSClassFromString(className);
	if (targetClass == Nil) {
		return nil;
	}

	for (NSString *selectorName in @[@"sharedInstanceIfExists", @"sharedInstance"]) {
		id instance = RFInvokeObjectSelector(targetClass, selectorName);
		if (instance != nil) {
			return instance;
		}
	}

	return nil;
}

NSArray *RFDisplayedIconViews(id iconManager) {
	if (iconManager == nil) {
		return @[];
	}

	SEL selector = NSSelectorFromString(@"enumerateDisplayedIconViewsUsingBlock:");
	if (![iconManager respondsToSelector:selector]) {
		return @[];
	}

	NSMethodSignature *signature = [iconManager methodSignatureForSelector:selector];
	if (signature == nil || signature.numberOfArguments != 3) {
		return @[];
	}

	const char *returnType = RFSkipTypeQualifiers(signature.methodReturnType);
	const char *argumentType = RFSkipTypeQualifiers([signature getArgumentTypeAtIndex:2]);
	if (returnType[0] != 'v' || argumentType[0] != '@') {
		return @[];
	}

	NSMutableArray *views = [NSMutableArray array];
	void (^collector)(id, BOOL *) = ^(id iconView, BOOL *stop) {
		(void)stop;
		if (iconView != nil) {
			[views addObject:iconView];
		}
	};

	void (*sendBlock)(id, SEL, id) = (void (*)(id, SEL, id))objc_msgSend;
	@try {
		sendBlock(iconManager, selector, collector);
	} @catch (__unused NSException *exception) {
		return @[];
	}

	return [views copy];
}
