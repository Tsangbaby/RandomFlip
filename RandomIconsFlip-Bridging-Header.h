#pragma once

#import <Foundation/Foundation.h>

NS_ASSUME_NONNULL_BEGIN

#ifdef __cplusplus
extern "C" {
#endif

FOUNDATION_EXPORT NSNumber * _Nullable RFReadBoolSelector(
	id _Nullable object,
	NSString *selectorName
);

FOUNDATION_EXPORT id _Nullable RFInvokeObjectSelector(
	id _Nullable object,
	NSString *selectorName
);

FOUNDATION_EXPORT id _Nullable RFSharedInstanceForClassNamed(
	NSString *className
);

FOUNDATION_EXPORT NSArray *RFDisplayedIconViews(
	id _Nullable iconManager
);

#ifdef __cplusplus
}
#endif

NS_ASSUME_NONNULL_END
