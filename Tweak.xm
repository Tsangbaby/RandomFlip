#import <UIKit/UIKit.h>
#import <RandomIconsFlip-Swift.h>

%hook SpringBoard

- (void)applicationDidFinishLaunching:(id)application {
	%orig;

	dispatch_async(dispatch_get_main_queue(), ^{
		[[RandomFlipManager sharedManager] start];
	});
}

%end
