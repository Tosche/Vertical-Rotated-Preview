# encoding: utf-8


from __future__ import print_function, unicode_literals
from GlyphsApp import Glyphs, UPDATEINTERFACE, DOCUMENTACTIVATED, TABDIDOPEN, TABWILLCLOSE, WINDOW_MENU, LTR, GSControlLayer
from GlyphsApp.plugins import GeneralPlugin
import vanilla
from AppKit import (
	NSAffineTransform,
	NSView,
	NSScrollView,
	NSColor,
	NSBezierPath,
	NSMenuItem,
	NSEvent,
	NSEventModifierFlagOption,
	NSApp, # for checking dark mode
	NSAppearanceNameAqua, # for checking dark mode
	NSAppearanceNameDarkAqua # for checking dark mode
	)
from Foundation import NSWidth, NSHeight, NSMidX, NSMidY
import traceback
import re, objc

surrogate_pairs = re.compile(u'[\ud800-\udbff][\udc00-\udfff]', re.UNICODE)
surrogate_start = re.compile(u'[\ud800-\udbff]', re.UNICODE)
emoji_variation_selector = re.compile(u'[\ufe00-\ufe0f]', re.UNICODE)


def is_glyphs_dark_ui():
    app = NSApp()
    if app is None:
        return False
    match = app.effectiveAppearance().bestMatchFromAppearancesWithNames_(
        [NSAppearanceNameAqua, NSAppearanceNameDarkAqua]
    )
    return match == NSAppearanceNameDarkAqua


class VerticalRotatedPreviewView(NSView):

	@objc.python_method
	def getLineBrokenLayers(self, font) -> list:
		"""
		Returns a list of line-broken layers
		because Glyphs currently does not provide it officially.
		"""
		lineWidthMax = Glyphs.editViewWidth # read only
		lineWidthCurrent = 0 # gets reset every time a line break is added
		lineBrokenLayers = [] # list of layers to return
		for l in font.currentTab.layers:
			if lineWidthCurrent + l.width > lineWidthMax:
				# layer width is going to exceed max
				lineWidthCurrent = 0
				if l.category == 'Separator': # if a space etc breaks the line, add 'break' instead
					lineBrokenLayers.append('break')
				else:
					lineBrokenLayers.append(l)
			else:
				lineWidthCurrent += l.width
				lineBrokenLayers.append(l)
		return lineBrokenLayers
		# 'break' or GSControlLayer is the line break point


	@objc.python_method
	def getKernValue(self, layer1, layer2) -> int:
		if Glyphs.buildNumber > 3000:
			return int(layer1.nextKerningForLayer_direction_(layer2, LTR))
		else:
			return int(layer1.rightKerningForLayer_(layer2))


	@objc.python_method
	def getDrawingColours(self, font):
		try:
			colours = []
			for cp in ('Master Background Color Dark', 'Master Background Color', 'Master Color Dark', 'Master Color'):
				try:
					colours.append(font.selectedFontMaster.customParameters[cp])
				except:
					colours.append(None)

			if is_glyphs_dark_ui(): # dark mode
				if colours[0]: # if custom parameter exists
					self._backColour = NSColor.colorWithCalibratedRed_green_blue_alpha_(*colours[0])
				else:
					self._backColour = NSColor.blackColor()
				if colours[2]:
					self._foreColour = NSColor.colorWithCalibratedRed_green_blue_alpha_(*colours[2])
				else:
					self._foreColour = NSColor.whiteColor()
			else:
				if colours[1]:
					self._backColour = NSColor.colorWithCalibratedRed_green_blue_alpha_(*colours[1])
				else:
					self._backColour = NSColor.whiteColor()
				if colours[3]:
					self._foreColour = NSColor.colorWithCalibratedRed_green_blue_alpha_(*colours[3])
				else:
					self._foreColour = NSColor.blackColor()
		except:
			# print(traceback.format_exc())
			self._backColour = NSColor.whiteColor()
			self._foreColour = NSColor.blackColor()

	@objc.python_method
	def addLinePath(self, fullPath, linePath, lineOffsetY):
		try:
			if linePath.isEmpty():
				return
			# Each new line needs its own accumulated offset. Using a constant offset
			# puts every appended path at the same coordinates.
			transform = NSAffineTransform.transform()
			lineOffsetY = lineOffsetY if Glyphs.defaults["com.Tosche.VerticalRotatedPreview.lineDir"] == 0 else -lineOffsetY
			transform.translateXBy_yBy_(0, lineOffsetY)
			linePath.transformUsingAffineTransform_(transform)
			fullPath.appendBezierPath_(linePath)
		except:
			# print(traceback.format_exc())
			pass

	def mouseDown_(self, event):
		try:
			scrollView = self.enclosingScrollView()
			if scrollView is None:
				return
			clipView = scrollView.contentView()
			clipOrigin = clipView.bounds().origin
			self._dragStartPoint = event.locationInWindow()
			self._dragStartOrigin = (clipOrigin.x, clipOrigin.y)
		except:
			print(traceback.format_exc())

	def mouseDragged_(self, event):
		try:
			if not hasattr(self, "_dragStartPoint") or not hasattr(self, "_dragStartOrigin"):
				return
			scrollView = self.enclosingScrollView()
			if scrollView is None:
				return

			clipView = scrollView.contentView()
			docView = scrollView.documentView()
			if docView is None:
				return

			currentPoint = event.locationInWindow()
			dx = currentPoint.x - self._dragStartPoint.x
			dy = currentPoint.y - self._dragStartPoint.y

			startX, startY = self._dragStartOrigin
			newX = startX - dx
			newY = startY - dy

			docSize = docView.frame().size
			clipSize = clipView.bounds().size
			maxX = max(0, docSize.width - clipSize.width)
			maxY = max(0, docSize.height - clipSize.height)

			newX = max(0, min(newX, maxX))
			newY = max(0, min(newY, maxY))

			clipView.scrollToPoint_((newX, newY))
			scrollView.reflectScrolledClipView_(clipView)
		except:
			print(traceback.format_exc())

	@objc.python_method
	def updateScale_(self, delta): # for option + scroll wheel zooming
		try:
			preferenceKey = "com.Tosche.VerticalRotatedPreview.scale"
			currentScale = Glyphs.defaults[preferenceKey]
			if currentScale is None:
				currentScale = 0.5
			step = 0.03 # adjust this for faster/slower zooming
			newScale = currentScale + (delta * step)
			newScale = max(0.1, min(newScale, 1.0))
			Glyphs.defaults[preferenceKey] = newScale

			wrapper = getattr(self, "wrapper", None)
			if wrapper is None:
				self.setNeedsDisplay_(True)
				return

			windowController = getattr(wrapper, "_windowController", None)
			if windowController is not None and hasattr(windowController, "scaleSlider"):
				windowController.scaleSlider.set(newScale)
			wrapper.redraw()
		except:
			# print(traceback.format_exc())
			pass

	def scrollWheel_(self, event): # for option + scroll wheel zooming
		try:
			optionKeyPressed = event.modifierFlags() & NSEventModifierFlagOption == NSEventModifierFlagOption
			if not optionKeyPressed:
				return NSView.scrollWheel_(self, event)

			deltaY = event.scrollingDeltaY()
			if deltaY == 0:
				return

			# Natural scrolling may invert direction; using the sign is enough here.
			direction = 1 if deltaY > 0 else -1
			self.updateScale_(direction)
		except:
			# print(traceback.format_exc())
			pass

	def drawRect_(self, rect):
		"""
		Gets called whenever the view needs to be redrawn. This is where you should put your drawing code.
		"""
		try:
			font = Glyphs.font
			self.getDrawingColours(font)
			self._backColour.set()
			NSBezierPath.fillRect_(self.bounds()) # fill the background with the background colour

			if font.currentTab is None:
				return

			fullPath = NSBezierPath.alloc().init()
			linePath = NSBezierPath.alloc().init()
			layers = self.getLineBrokenLayers(font)
			advance = 0
			lineOffsetY = 0
			lineHeight = font.selectedFontMaster.ascender - font.selectedFontMaster.descender
			# linebreak_direction = Glyphs.defaults["com.Tosche.VerticalRotatedPreview.lineDir"] or 0
			for i, l in enumerate(layers):
				# print(i, l)
				if l == 'break' or type(l) == GSControlLayer:
					advance = 0
					self.addLinePath(fullPath, linePath, lineOffsetY)
					lineOffsetY += lineHeight
					linePath = NSBezierPath.alloc().init()
				else:
					kernValue = 0
					if layers[i-1] != 'break' and type(layers[i-1]) != GSControlLayer and i > 0:
						kernValue = self.getKernValue(layers[i-1], l)
						if kernValue > 10000:
							kernValue = 0
					transform = NSAffineTransform.transform()
					transform.translateXBy_yBy_(advance, 0)
					layerPath = l.completeBezierPath
					layerPath.transformUsingAffineTransform_( transform )
					linePath.appendBezierPath_(layerPath)
					advance += l.width + kernValue
			self.addLinePath(fullPath, linePath, lineOffsetY)

			if fullPath.isEmpty():
				return

			# scale = font.currentTab.scale
			scale = Glyphs.defaults["com.Tosche.VerticalRotatedPreview.scale"]

			transform = NSAffineTransform.transform()
			transform.rotateByDegrees_(-90)
			transform.scaleBy_(scale)
			fullPath.transformUsingAffineTransform_(transform)

			# Grow the document view to fit the content, then draw at a fixed margin.
			bounds = fullPath.bounds()
			margin = 300 # maybe respond to scale
			contentW = NSWidth(bounds) + 2 * margin
			contentH = NSHeight(bounds) + 2 * margin

			# Keep the document view at least as large as the visible scroll viewport.
			scrollView = self.enclosingScrollView()
			if scrollView is not None:
				clipSize = scrollView.contentSize()
				contentW = max(contentW, clipSize.width)
				contentH = max(contentH, clipSize.height)

			currentFrame = self.frame()
			if abs(currentFrame.size.width - contentW) > 1 or abs(currentFrame.size.height - contentH) > 1:
				self.setFrameSize_((contentW, contentH))

			# Place content at (margin, margin) from bottom-left of document view.
			transform = NSAffineTransform.transform()
			transform.translateXBy_yBy_(
				-bounds.origin.x + margin,
				-bounds.origin.y + margin,
			)
			fullPath.transformUsingAffineTransform_(transform)

			self._foreColour.set()
			fullPath.fill()
		except:
			# print(traceback.format_exc())
			pass




class TheView(vanilla.VanillaBaseObject):
	"""
	Vanilla-wrapped view for the VerticalRotatedPreview which is a NSView subclass.
	The preview NSView lives as the document view inside an NSScrollView.
	"""

	def __init__(self, posSize):
		# Create the scroll view as the vanilla-managed object
		self._setupView(NSScrollView, posSize)
		scrollView = self._nsObject

		# Create the preview as the scroll view's document view
		initialFrame = ((0, 0), (400, 400))
		previewView = VerticalRotatedPreviewView.alloc().initWithFrame_(initialFrame)
		previewView.wrapper = self
		self._windowController = None
		self._previewView = previewView

		scrollView.setDocumentView_(previewView)
		scrollView.setHasVerticalScroller_(True)
		scrollView.setHasHorizontalScroller_(True)
		scrollView.setAutohidesScrollers_(True)

	def redraw(self):
		self._previewView.setNeedsDisplay_(True)

	def scrollToTop(self):
		"""Scroll so the top of the content is visible (called once on window open)."""
		sv = self._nsObject
		dv = sv.documentView()
		docH = dv.frame().size.height
		clipH = sv.contentSize().height
		topY = max(0, docH - clipH)
		dv.scrollPoint_((0, topY))




class VerticalRotatedPreview(GeneralPlugin):
	@objc.python_method
	def settings(self):
		self.name = Glyphs.localize({'en': u'Vertical Rotated Preview Window'})
		self.w = None
		self._callbacksRegistered = False


	def showWindow_(self, sender):
		try:
			if self.w is not None:
				self.w.open()
				self.redrawPreview_(None)
				return

			self.windowWidth = 400
			self.windowHeight = 240
			windowSize = (self.windowWidth, self.windowHeight)
			windowTitle = "Vertical Rotated Preview"
			autosaveName = "com.Tosche.VerticalRotatedPreview.window"
			keysPressed = NSEvent.modifierFlags()
			optionKeyPressed = keysPressed & NSEventModifierFlagOption == NSEventModifierFlagOption
			if optionKeyPressed:
				self.w = vanilla.FloatingWindow(windowSize, windowTitle, minSize=windowSize, autosaveName=autosaveName)
			else:
				self.w = vanilla.Window(windowSize, windowTitle, minSize=windowSize, autosaveName=autosaveName)

			self.w.preview = TheView('auto')
			self.w.preview._windowController = self.w
			self.w.lineDirText = vanilla.TextBox('auto', "Line Break Direction:")
			self.w.lineDirRadio = vanilla.RadioGroup('auto', ["LTR→", "←RTL"], isVertical=False, callback=self.uiChanged_)
			self.w.scaleText = vanilla.TextBox('auto', "Scale:")
			self.w.scaleSlider = vanilla.Slider('auto', minValue=0.1, maxValue=1.0, value=0.5, callback=self.uiChanged_)
			rules = [
				'H:|[preview]|',
				'H:|-[lineDirText]-[lineDirRadio(130)]-[scaleText]-[scaleSlider]-|',
				'V:|[preview]-[lineDirText]-|',
				'V:|[preview]-[lineDirRadio]-|',
				'V:|[preview]-[scaleText]-|',
				'V:|[preview]-[scaleSlider]-|',
			]
			self.w.addAutoPosSizeRules(rules)
			self.w.bind("close", self.windowClosed_)
			self.loadPrefs()
			self.w.open()
			self.redrawPreview_(None)
			self.w.preview.scrollToTop()

		except:
			# print(traceback.format_exc())
			pass


	@objc.python_method
	def loadPrefs(self):
		try:
			if Glyphs.defaults["com.Tosche.VerticalRotatedPreview.lineDir"] is None:
				Glyphs.defaults["com.Tosche.VerticalRotatedPreview.lineDir"] = 0
				Glyphs.defaults["com.Tosche.VerticalRotatedPreview.scale"] = 0.5
			self.w.lineDirRadio.set(Glyphs.defaults["com.Tosche.VerticalRotatedPreview.lineDir"])
			self.w.scaleSlider.set(Glyphs.defaults["com.Tosche.VerticalRotatedPreview.scale"])
		except:
			# print(traceback.format_exc())
			pass


	def uiChanged_(self, sender):
		try:
			Glyphs.defaults["com.Tosche.VerticalRotatedPreview.lineDir"] = self.w.lineDirRadio.get()
			Glyphs.defaults["com.Tosche.VerticalRotatedPreview.scale"] = self.w.scaleSlider.get()

			self.w.preview.redraw()
		except:
			# print(traceback.format_exc())
			pass

	@objc.python_method
	def redrawPreview_(self, sender):
		try:
			if self.w is None:
				return
			if not hasattr(self.w, "preview"):
				return
			self.w.preview.redraw()
		except:
			# print(traceback.format_exc())
			pass


	def changeDocument_(self, sender):
		"""
		Update when current document changes (choosing another open Font)
		"""
		self.redrawPreview_(sender)

	@objc.python_method
	def registerCallbacks(self):
		if self._callbacksRegistered:
			return
		Glyphs.addCallback(self.redrawPreview_, UPDATEINTERFACE)
		Glyphs.addCallback(self.redrawPreview_, DOCUMENTACTIVATED)
		Glyphs.addCallback(self.redrawPreview_, TABDIDOPEN)
		Glyphs.addCallback(self.redrawPreview_, TABWILLCLOSE)
		self._callbacksRegistered = True


	@objc.python_method
	def start(self):
		newMenuItem = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(self.name, self.showWindow_, "")
		newMenuItem.setTarget_(self)
		Glyphs.menu[WINDOW_MENU].append(newMenuItem)
		self.registerCallbacks()

	def setWindowController_(self, windowController):
		try:
			self._windowController = windowController
		except:
			# self.logError(traceback.format_exc())
			pass

	def windowClosed_(self, sender):
		self.w = None


	@objc.python_method
	def __del__(self):
		Glyphs.removeCallback(self.redrawPreview_)

	def __file__(self):
		"""Please leave this method unchanged"""
		return __file__