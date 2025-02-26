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
import threading
import time
from threading import Thread
import copy
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
		
		# キャッシュの初期化
		self.cache = {}
		self.lastModificationDates = {}
		self.cachedGuideColor = {}
		self.cachedLineStyle = {}
		self.lock = threading.Lock()  # スレッドセーフのためのロック
		
		# 非同期処理のためのフラグとキャッシュ
		self.isUpdating = False
		self.backgroundCache = {}
		self.lastRedrawTime = 0
		self.updateInterval = 0.1  # 更新間隔（秒）
		self.asyncWorker = None
		self.currentLayerInfo = None

	@objc.python_method
	def parameterChanged(self, font, paramName):
		"""パラメータが変更されたかチェック"""
		if not font or not paramName:
			return True
			
		# カスタムパラメータの現在の値を取得
		currentValue = None
		if paramName in font.customParameters:
			currentValue = font.customParameters[paramName]
			
		# キャッシュと比較
		cachedValue = self.cachedGuideColor.get(paramName) if 'Guide Color' in paramName else self.cachedLineStyle.get(paramName)
		
		# 値が変更された場合、キャッシュを更新して True を返す
		if cachedValue != currentValue:
			if 'Guide Color' in paramName:
				self.cachedGuideColor[paramName] = currentValue
			else:
				self.cachedLineStyle[paramName] = currentValue
			return True
			
		return False

	@objc.python_method
	def needsUpdateForFont(self, font):
		"""フォントのカスタムパラメータが変更されたかチェック"""
		if not font:
			return True
			
		# 基本パラメータをチェック
		needsUpdate = self.parameterChanged(font, "Guide Color") or self.parameterChanged(font, "Line Style")
		
		# サフィックス付きパラメータをチェック - カスタムパラメータを安全に検出
		try:
			# CustomParametersProxyをイテレートする適切な方法
			for param in font.customParameters:
				paramName = param.name if hasattr(param, 'name') else str(param)
				if paramName.startswith("Guide Color:") or paramName.startswith("Line Style:"):
					if self.parameterChanged(font, paramName):
						needsUpdate = True
		except:
			# イテレーションに失敗した場合は、更新が必要と判断
			needsUpdate = True
					
		return needsUpdate

	@objc.python_method
	def needsUpdateForGlyph(self, glyph):
		"""グリフが変更されたかチェック"""
		if not glyph:
			return False
			
		# 単純なタイムスタンプ比較ではなく、グリフのIDと修正回数を使用
		try:
			cacheKey = str(glyph.id) if hasattr(glyph, 'id') else glyph.name
			currentModCount = id(glyph)  # 最もシンプルな比較方法として、IDを使用
		except:
			# 何らかのエラーが発生した場合は、更新が必要と判断
			return True
		
		lastModCount = self.lastModificationDates.get(cacheKey)
		if lastModCount != currentModCount:
			self.lastModificationDates[cacheKey] = currentModCount
			return True
		return False
		
	@objc.python_method
	def asyncUpdateGuidePaths(self, layerInfo):
		"""バックグラウンドスレッドでガイドパスを更新"""
		try:
			layer, masterId, scale = layerInfo
			guidePaths = self.calculateGuidePaths(layer, masterId, scale)
			
			# メインスレッドのキャッシュを更新
			with self.lock:
				cacheKey = (masterId, layer.parent.name if layer and layer.parent else None)
				self.backgroundCache[cacheKey] = guidePaths
				
		except Exception as e:
			print("asyncUpdateGuidePaths error:", str(e))
		finally:
			self.isUpdating = False

	@objc.python_method
	def getGuidePathsForLayer(self, layer, masterId, scale):
		"""レイヤーに対するガイドパスを取得（キャッシュ使用）"""
		if not layer or not layer.parent:
			return None
			
		# キャッシュキーの生成
		cacheKey = (masterId, layer.parent.name)
		
		# 現在のレイヤー情報を保存
		self.currentLayerInfo = (layer, masterId, scale)
		
		# 非同期更新の必要性をチェック
		currentTime = time.time()
		needsAsyncUpdate = False
		
		# ガイドパスがキャッシュになければ、非同期更新を開始
		if cacheKey not in self.backgroundCache:
			needsAsyncUpdate = True
		# 前回の更新から一定時間が経過していたら、バックグラウンドで更新
		elif currentTime - self.lastRedrawTime > self.updateInterval:
			script = layer.parent.script
			category = layer.parent.category
			font = layer.parent.parent
			
			# フォントパラメータや関連ガイドグリフに変更があるかチェック
			if self.needsUpdateForFont(font):
				needsAsyncUpdate = True
			else:
				# ガイドグリフの変更をチェック
				possibleNames = []
				if script:
					possibleNames.append('_guide.' + script)
				if category:
					possibleNames.append('_guide.' + category)
				if script and category:
					possibleNames.append('_guide.' + script + '.' + category)
					possibleNames.append('_guide.' + category + '.' + script)
				
				for name in possibleNames:
					guideGlyph = font.glyphs[name]
					if guideGlyph and self.needsUpdateForGlyph(guideGlyph):
						needsAsyncUpdate = True
						break
				
				# カスタムガイドグリフの変更をチェック
				if not needsAsyncUpdate:
					for glyph in font.glyphs:
						if glyph.name.startswith('_guide.') and '.c_' in glyph.name:
							if self.needsUpdateForGlyph(glyph):
								needsAsyncUpdate = True
								break
		
		# 非同期更新を開始（既に更新中でなければ）
		if needsAsyncUpdate and not self.isUpdating:
			self.isUpdating = True
			self.lastRedrawTime = currentTime
			
			# 別スレッドで更新処理を開始
			worker = Thread(target=self.asyncUpdateGuidePaths, args=(self.currentLayerInfo,))
			worker.daemon = True
			worker.start()
		
		# 現在のキャッシュを返す（あれば）
		return self.backgroundCache.get(cacheKey)

	@objc.python_method
	def calculateGuidePaths(self, layer, masterId, scale):
		"""ガイドパスの計算（非同期処理用）"""
		if not layer or not layer.parent:
			return None
			
		script = layer.parent.script
		category = layer.parent.category
		
		# ガイドグリフを収集
		guideGlyphs = []
		possibleNames = []
		
		if script:
			possibleNames.append('_guide.' + script)
		if category:
			possibleNames.append('_guide.' + category)
		if script and category:
			possibleNames.append('_guide.' + script + '.' + category)
			possibleNames.append('_guide.' + category + '.' + script)

		# カスタムガイドグリフを追加
		font = layer.parent.parent
		for glyph in font.glyphs:
			if glyph.name.startswith('_guide.') and '.c_' in glyph.name:
				possibleNames.append(glyph.name)
		
		# ガイドグリフを収集
		for name in possibleNames:
			guideGlyph = font.glyphs[name]
			if guideGlyph:
				guideGlyphs.append(guideGlyph)

		# 一般的なガイドグリフにフォールバック
		if not guideGlyphs:
			guideGlyph = font.glyphs['_guide.any']
			if guideGlyph:
				guideGlyphs.append(guideGlyph)

		if not guideGlyphs:
			return None
		
		# パスの計算
		guidePaths = []
		
		for guideGlyph in guideGlyphs:
			guideLayer = guideGlyph.layers[masterId]
			if guideLayer is None:
				continue
				
			colorSuffix = guideGlyph.name.split('.c_')[-1] if '.c_' in guideGlyph.name else None
			closedLineStyle = self.getLineStyle(colorSuffix, "closed")
			openLineStyle = self.getLineStyle(colorSuffix, "open")
			
			closedColor = self.getColorBySuffix(colorSuffix, 1, 0.35) if colorSuffix else self.getColor(1, 0.35)
			openColor = self.getColorBySuffix(colorSuffix, 0, 0.35) if colorSuffix else self.getColor(0, 0.35)
			
			try:
				# より効率的なパスのコピー
				closedPath = guideLayer.completeBezierPath
				openPath = guideLayer.completeOpenBezierPath
				
				# 処理中にパスが変更されないようにディープコピー
				from objc import python_method
				if hasattr(closedPath, 'copy'):
					closedPath = closedPath.copy()
				if hasattr(openPath, 'copy'):
					openPath = openPath.copy()
				
				# パスとその属性を保存
				guidePaths.append({
					'closed': {
						'path': closedPath,
						'color': closedColor,
						'style': closedLineStyle
					},
					'open': {
						'path': openPath,
						'color': openColor,
						'style': openLineStyle
					},
					'annotations': guideLayer.annotations
				})
			except Exception as e:
				print("Error processing guide glyph:", str(e))
				
		return guidePaths

	@objc.python_method
	def optimizePathsForScale(self, guidePaths, scale):
		"""スケールに応じてパスを最適化（小さなスケールでは簡略化）"""
		if not guidePaths or scale > 0.5:  # 十分な拡大率の場合は最適化しない
			return guidePaths
			
		optimizedPaths = []
		for guide in guidePaths:
			try:
				# クローンを作成して元のデータを保持
				optimizedGuide = copy.deepcopy(guide)
				
				# スケールが小さい場合、アノテーションをスキップ
				if scale < 0.3:
					optimizedGuide['annotations'] = []
					
				optimizedPaths.append(optimizedGuide)
			except:
				optimizedPaths.append(guide)  # エラー時は元のパスを使用
				
		return optimizedPaths

	@objc.python_method
	def background(self, layer):
		masterId = layer.associatedMasterId
		scale = self.getScale()
		if scale < 0.25:
			return

		# ガイドパスを取得（非同期更新も含む）
		guidePaths = self.getGuidePathsForLayer(layer, masterId, scale)
		if not guidePaths:
			return
			
		# スケールに応じてパスを最適化
		optimizedPaths = self.optimizePathsForScale(guidePaths, scale)

		# ガイドパスを描画
		for guide in optimizedPaths:
			try:
				# 閉じたパスを描画
				closedPathInfo = guide['closed']
				closedPath = closedPathInfo['path']
				closedColor = closedPathInfo['color']
				closedLineStyle = closedPathInfo['style']
				
				closedColor.set()
				closedPath.setLineWidth_(1.0 / scale)
				if closedLineStyle == "dotted":
					closedPath.setLineDash_count_phase_([6.0 / scale, 3.0 / scale], 2, 0)
				closedPath.stroke()
				
				# 開いたパスを描画
				openPathInfo = guide['open']
				openPath = openPathInfo['path']
				openColor = openPathInfo['color']
				openLineStyle = openPathInfo['style']
				
				openColor.set()
				openPath.setLineWidth_(1.0 / scale)
				if openLineStyle == "dotted":
					openPath.setLineDash_count_phase_([6.0 / scale, 3.0 / scale], 2, 0)
				openPath.stroke()
				
				# アノテーションを描画（拡大率が十分あれば）
				if scale >= 0.3:
					annotations = guide['annotations']
					if annotations:
						for ann in annotations:
							if ann.type != TEXT:
								continue
							if ann.text is None:
								continue
							self.drawTextAtPoint(
								ann.text, ann.position,
								fontSize=10,
								fontColor=openColor,
								align="topleft",
							)
						
			except Exception as e:
				self.logToConsole("showGuideSheets: %s\n" % str(e))
				import traceback
				print(traceback.format_exc())

		# パス上のノードをハイライト表示（拡大時のみ）
		if scale > 0.4:
			try:
				# ノードの位置を先にリスト化して効率的に処理
				nodePositions = []
				for path in layer.paths:
					for node in path.nodes:
						if node.type != OFFCURVE:
							nodePositions.append(node.position)
				
				# 位置ごとに一度だけチェック
				for pos in nodePositions:
					for guide in optimizedPaths:
						closedPath = guide['closed']['path']
						openPath = guide['open']['path']
						
						if closedPath.isStrokeHitByPoint_padding_(pos, .6):
							self.drawOnPathPoint(pos, self.getColor(1, 0.25), scale)
							break  # このノードはすでに描画したので次へ
						elif openPath.isStrokeHitByPoint_padding_(pos, .6):
							self.drawOnPathPoint(pos, self.getColor(0, 0.25), scale)
							break  # このノードはすでに描画したので次へ
			except Exception as e:
				self.logToConsole("showGuideSheetNodes: %s\n" % str(e))
				import traceback
				print(traceback.format_exc())

	@objc.python_method
	def drawOnPathPoint(self, pos, color, scale):
		r = RADIUS * 1.0 / scale
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
