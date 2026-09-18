#pragma once

#import <Foundation/Foundation.h>

NS_ASSUME_NONNULL_BEGIN

#ifdef __cplusplus
extern "C" {
#endif

FOUNDATION_EXPORT void RFTransitionDiagnosticsStart(void);
FOUNDATION_EXPORT NSString *RFTransitionDiagnosticsOutputPath(void);

#ifdef __cplusplus
}
#endif

NS_ASSUME_NONNULL_END
