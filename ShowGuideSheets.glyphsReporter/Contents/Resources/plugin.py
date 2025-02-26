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

		if not hasattr(self, 'cachedGuideGlyphs') or self.cachedGuideGlyphs is None:
			self.cachedGuideGlyphs = {}
		
		cacheKey = f"{script}_{category}_{masterId}"
		if cacheKey in self.cachedGuideGlyphs:
			guideGlyphs = self.cachedGuideGlyphs[cacheKey]
		else:
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
					
			# キャッシュに保存
			self.cachedGuideGlyphs[cacheKey] = guideGlyphs

		if not guideGlyphs:
			return

		# スケールに応じて処理を調整
		showNodes = scale > 0.4
		
		# Iterate over all collected guide glyphs
		for guideGlyph in guideGlyphs:
			guideLayer = guideGlyph.layers[masterId]
			if guideLayer is None:
				continue

			# パスの計算は必要な場合のみ行う
			closedPaths = guideLayer.completeBezierPath.copy()
			opendPath = guideLayer.completeOpenBezierPath.copy()
			
			if closedPaths is None and opendPath is None:
				continue

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
				# closedPathsが存在する場合のみ処理
				if closedPaths:
					color.set()
					closedPaths.setLineWidth_(1.0 / scale)
					if closedLineStyle == "dotted":
						closedPaths.setLineDash_count_phase_([6.0 / scale, 3.0 / scale], 2, 0)
					closedPaths.stroke()

				# opendPathが存在する場合のみ処理
				if opendPath:
					color = self.getColor(0, 0.35) if not colorSuffix else self.getColorBySuffix(colorSuffix, 0, 0.35)
					color.set()
					opendPath.setLineWidth_(1.0 / scale)
					if openLineStyle == "dotted":
						opendPath.setLineDash_count_phase_([6.0 / scale, 3.0 / scale], 2, 0)
					opendPath.stroke()

				# アノテーションの表示を最適化
				if guideLayer.annotations and scale > 0.3:
					for ann in guideLayer.annotations:
						if ann.type != TEXT or ann.text is None:
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

			# show on-path nodes - スケールが十分大きい場合のみ
			if showNodes:
				try:
					for path in layer.paths:
						for node in path.nodes:
							if node.type == OFFCURVE:
								continue
							# パスが存在する場合のみチェック
							if closedPaths and closedPaths.isStrokeHitByPoint_padding_(node.position, .6):
								self.drawOnPathPoint(node.position, self.getColor(1, 0.25), scale)
							elif opendPath and opendPath.isStrokeHitByPoint_padding_(node.position, .6):
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
		# キャッシュを使用して色の計算を最適化
		if not hasattr(self, 'colorCache'):
			self.colorCache = {}
		
		cacheKey = f"{index}_{alpha}"
		if cacheKey in self.colorCache:
			return self.colorCache[cacheKey]
			
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
			color = NSColor.colorWithRed_green_blue_alpha_(r, g, b, alpha)
		except:
			color = NSColor.colorWithRed_green_blue_alpha_(0.1, 0.6, 0.8, alpha)
			
		# キャッシュに保存
		self.colorCache[cacheKey] = color
		return color

	@objc.python_method
	def getColorBySuffix(self, suffix, index, alpha):
		# キャッシュを使用して色の計算を最適化
		if not hasattr(self, 'colorSuffixCache'):
			self.colorSuffixCache = {}
		
		cacheKey = f"{suffix}_{index}_{alpha}"
		if cacheKey in self.colorSuffixCache:
			return self.colorSuffixCache[cacheKey]
			
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
			color = NSColor.colorWithRed_green_blue_alpha_(r, g, b, alpha)
		except:
			color = NSColor.colorWithRed_green_blue_alpha_(0.1, 0.6, 0.8, alpha)
			
		# キャッシュに保存
		self.colorSuffixCache[cacheKey] = color
		return color

	@objc.python_method
	def getLineStyle(self, suffix, pathType):
		# キャッシュを使用してスタイルの計算を最適化
		if not hasattr(self, 'lineStyleCache'):
			self.lineStyleCache = {}
		
		cacheKey = f"{suffix}_{pathType}"
		if cacheKey in self.lineStyleCache:
			return self.lineStyleCache[cacheKey]
			
		# カスタムパラメーターから線のスタイルを取得
		paramName = f"Line Style:{suffix}" if suffix else "Line Style"
		if paramName in Glyphs.font.customParameters:
			lineStyle = Glyphs.font.customParameters[paramName]
		else:
			lineStyle = "solid"
		styles = lineStyle.split(",")

		# パラメーターが1つしかない場合、両方に適用
		if len(styles) == 1:
			result = styles[0].strip()
		# パスの種類に応じてスタイルを返す
		elif pathType == "closed":
			result = styles[1].strip() if len(styles) > 1 else styles[0].strip()
		elif pathType == "open":
			result = styles[0].strip()
		else:
			result = "solid"
			
		# キャッシュに保存
		self.lineStyleCache[cacheKey] = result
		return result

	@objc.python_method
	def __file__(self):
		"""Please leave this method unchanged"""
		return __file__
