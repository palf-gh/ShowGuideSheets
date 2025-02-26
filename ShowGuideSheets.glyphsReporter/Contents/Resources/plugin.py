# encoding: utf-8

###########################################################################################################
#
#
# Reporter Plugin
#
# Read the docs:
# https://github.com/schriftgestalt/GlyphsSDK/tree/master/Python%20Templates/Reporter
#
#
###########################################################################################################


from __future__ import division, print_function, unicode_literals
import objc
from GlyphsApp import Glyphs, OFFCURVE, TEXT
from GlyphsApp.plugins import ReporterPlugin
from AppKit import NSRect, NSPoint, NSSize, NSColor, NSBezierPath
RADIUS = 9


class ShowGuideSheets(ReporterPlugin):

	@objc.python_method
	def settings(self):
		self.menuName = Glyphs.localize({
			'en': 'Guide Sheets',
			'zh-Hant': '稿紙',
			'zh-Hant-TW': '稿紙',
			'zh-Hans': '稿纸',
			'zh': '稿紙',
			'ja': '原稿用紙',
		})

	@objc.python_method
	def background(self, layer):
		script = layer.parent.script
		category = layer.parent.category
		masterId = layer.associatedMasterId
		scale = self.getScale()
		if scale < 0.25:
			return

		guideGlyphs = []
		# Collect all possible guide glyph names
		possibleNames = []
		if script:
			possibleNames.append('_guide.' + script)
		if category:
			possibleNames.append('_guide.' + category)
		if script and category:
			possibleNames.append('_guide.' + script + '.' + category)
			possibleNames.append('_guide.' + category + '.' + script)

		# Add custom guide glyphs with .c_[name] suffix
		for glyph in Glyphs.font.glyphs:
			if glyph.name.startswith('_guide.') and '.c_' in glyph.name:
				possibleNames.append(glyph.name)

		# Collect all guide glyphs
		for name in possibleNames:
			guideGlyph = Glyphs.font.glyphs[name]
			if guideGlyph:
				guideGlyphs.append(guideGlyph)

		# Fallback to a general guide glyph
		if not guideGlyphs:
			guideGlyph = Glyphs.font.glyphs['_guide.any']
			if guideGlyph:
				guideGlyphs.append(guideGlyph)

		if not guideGlyphs:
			return

		# Iterate over all collected guide glyphs
		for guideGlyph in guideGlyphs:
			guideLayer = guideGlyph.layers[masterId]
			if guideLayer is None:
				continue

			closedPaths = guideLayer.completeBezierPath.copy()
			opendPath = guideLayer.completeOpenBezierPath.copy()

			# Determine color based on custom parameter or default
			colorSuffix = guideGlyph.name.split('.c_')[-1] if '.c_' in guideGlyph.name else None
			if colorSuffix:
				color = self.getColorBySuffix(colorSuffix, 1, 0.35)
			else:
				color = self.getColor(1, 0.35)

			# Determine line style
			closedLineStyle = self.getLineStyle(colorSuffix, "closed")
			openLineStyle = self.getLineStyle(colorSuffix, "open")

			# show guides
			try:
				color.set()
				closedPaths.setLineWidth_(1.0 / scale)
				if closedLineStyle == "dotted":
					closedPaths.setLineDash_count_phase_([6.0 / scale, 3.0 / scale], 2, 0)
				closedPaths.stroke()

				color = self.getColor(0, 0.35) if not colorSuffix else self.getColorBySuffix(colorSuffix, 0, 0.35)
				color.set()
				opendPath.setLineWidth_(1.0 / scale)
				if openLineStyle == "dotted":
					opendPath.setLineDash_count_phase_([6.0 / scale, 3.0 / scale], 2, 0)
				opendPath.stroke()

				if guideLayer.annotations:
					for ann in guideLayer.annotations:
						if ann.type != TEXT:
							continue
						if ann.text is None:
							continue
						self.drawTextAtPoint(
								ann.text, ann.position,
								fontSize=10,
								fontColor=color,
								align="topleft",
							)

			except Exception as e:
				self.logToConsole("showGuideSheets: %s\n" % str(e))
				import traceback
				print(traceback.format_exc())

			# show on-path nodes
			if scale > 0.4:
				try:
					for path in layer.paths:
						for node in path.nodes:
							if node.type == OFFCURVE:
								continue
							if closedPaths.isStrokeHitByPoint_padding_(node.position, .6):
								self.drawOnPathPoint(node.position, self.getColor(1, 0.25), scale)
							if opendPath.isStrokeHitByPoint_padding_(node.position, .6):
								self.drawOnPathPoint(node.position, self.getColor(0, 0.25), scale)

				except Exception as e:
					self.logToConsole("showGuideSheetNodes: %s\n" % str(e))
					import traceback
					print(traceback.format_exc())

	@objc.python_method
	def drawOnPathPoint(self, pos, color, scale):
		r = RADIUS * 1.0 / scale
		# NSColor.colorWithRed_green_blue_alpha_(0.1, 0.6, 0.8, 0.25).set()
		# self.getColor(0.25).set()
		color.set()
		rect = NSRect(NSPoint(pos.x - r, pos.y - r), NSSize(r * 2, r * 2))
		circle = NSBezierPath.bezierPathWithRoundedRect_cornerRadius_(rect, r)
		circle.fill()

		NSColor.colorWithRed_green_blue_alpha_(1.0, 1.0, 1.0, 1.0).set()
		circle.setLineWidth_(1.0 / scale)
		circle.stroke()

	@objc.python_method
	def getColor(self, index, alpha):
		colorHex = Glyphs.font.customParameters["Guide Color"]

		try:
			if index == 1 and len(colorHex) >= 13:
				r = int(colorHex[7:9], 16) / 255.0
				g = int(colorHex[9:11], 16) / 255.0
				b = int(colorHex[11:13], 16) / 255.0
			else:
				r = int(colorHex[0:2], 16) / 255.0
				g = int(colorHex[2:4], 16) / 255.0
				b = int(colorHex[4:6], 16) / 255.0
			return NSColor.colorWithRed_green_blue_alpha_(r, g, b, alpha)
		except:
			return NSColor.colorWithRed_green_blue_alpha_(0.1, 0.6, 0.8, alpha)

	@objc.python_method
	def getColorBySuffix(self, suffix, index,  alpha):
		# Access custom parameters using dictionary-like indexing
		colorHex = Glyphs.font.customParameters[f"Guide Color:{suffix}"] if f"Guide Color:{suffix}" in Glyphs.font.customParameters else None

		try:
			if index == 1 and len(colorHex) >= 13:
				r = int(colorHex[7:9], 16) / 255.0
				g = int(colorHex[9:11], 16) / 255.0
				b = int(colorHex[11:13], 16) / 255.0
			else:
				r = int(colorHex[0:2], 16) / 255.0
				g = int(colorHex[2:4], 16) / 255.0
				b = int(colorHex[4:6], 16) / 255.0
			return NSColor.colorWithRed_green_blue_alpha_(r, g, b, alpha)
		except:
			return NSColor.colorWithRed_green_blue_alpha_(0.1, 0.6, 0.8, alpha)

	@objc.python_method
	def getLineStyle(self, suffix, pathType):
		# カスタムパラメーターから線のスタイルを取得
		paramName = f"Line Style:{suffix}" if suffix else "Line Style"
		if paramName in Glyphs.font.customParameters:
			lineStyle = Glyphs.font.customParameters[paramName]
		else:
			lineStyle = "solid"
		styles = lineStyle.split(",")

		# パラメーターが1つしかない場合、両方に適用
		if len(styles) == 1:
			return styles[0].strip()

		# パスの種類に応じてスタイルを返す
		if pathType == "closed":
			return styles[1].strip() if len(styles) > 1 else styles[0].strip()
		elif pathType == "open":
			return styles[0].strip()
		return "solid"

	@objc.python_method
	def __file__(self):
		"""Please leave this method unchanged"""
		return __file__
