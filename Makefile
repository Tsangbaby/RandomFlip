ARCHS = arm64 arm64e
TARGET = iphone:clang:latest:15.0
INSTALL_TARGET_PROCESSES = SpringBoard
PACKAGE_VERSION = 0.0.1

include $(THEOS)/makefiles/common.mk

TWEAK_NAME = RandomIconsFlip

RandomIconsFlip_FILES = Tweak.xm \
	RuntimeBridge.m \
	Sources/RandomFlipManager.swift \
	Sources/SpringBoardEnvironment.swift
RandomIconsFlip_CFLAGS = -fobjc-arc
RandomIconsFlip_SWIFTFLAGS = -O
RandomIconsFlip_FRAMEWORKS = Foundation UIKit QuartzCore

include $(THEOS_MAKE_PATH)/tweak.mk
