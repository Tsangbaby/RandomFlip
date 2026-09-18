#import <UIKit/UIKit.h>
#import <RandomIconsFlip-Swift.h>
#import "TransitionDiagnostics.h"

%hook SpringBoard

- (void)applicationDidFinishLaunching:(id)application {
	%orig;

	dispatch_async(dispatch_get_main_queue(), ^{
		[[RandomFlipManager sharedManager] start];
		@try {
			RFTransitionDiagnosticsStart();
		} @catch (__unused NSException *exception) {
			NSLog(@"[RFAppToHomeDiag] startupBoundaryException");
		}
	});
}

%end
