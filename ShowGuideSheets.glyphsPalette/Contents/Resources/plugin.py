# encoding: utf-8

###########################################################################################################
#
#
# Palette Plugin
# Companion palette for ShowGuideSheets — manage guide visibility, names,
# conditions and colors from a sidebar list. Layer-panel style UI built on
# NSOutlineView for collapsible condition groups, native disclosure
# triangles, eye-icon visibility toggle, and proper right-click menus.
#
#
###########################################################################################################


from __future__ import division, print_function, unicode_literals
import objc
import os
import traceback
from GlyphsApp import Glyphs, GSEditViewController, GSGlyph, UPDATEINTERFACE
from GlyphsApp.plugins import PalettePlugin
from AppKit import (
	NSAlert,
	NSAlertFirstButtonReturn,
	NSButton,
	NSColor,
	NSColorWell,
	NSEvent,
	NSFont,
	NSImage,
	NSImageAlignCenter,
	NSImageOnly,
	NSImageScaleProportionallyUpOrDown,
	NSMakeRect,
	NSMakeSize,
	NSMenu,
	NSMenuItem,
	NSMomentaryChangeButton,
	NSOutlineView,
	NSTableColumn,
	NSTableViewSelectionHighlightStyleSourceList,
	NSTextField,
	NSView,
	NSViewHeightSizable,
	NSViewMaxXMargin,
	NSViewMaxYMargin,
	NSViewMinXMargin,
	NSViewMinYMargin,
	NSViewWidthSizable,
	NSWarningAlertStyle,
)
from Foundation import NSIndexSet, NSObject
from vanilla import Button, Group, ScrollView, Window

print("ShowGuideSheetsPalette: plugin.py loaded")

HIDDEN_KEY = "ShowGuideSheets.hiddenGuides"
DISPLAYNAME_KEY = "ShowGuideSheets.displayName"
COLLAPSED_KEY = "ShowGuideSheets.collapsedGroups"

SHOW_COL_ID = "show"
NAME_COL_ID = "name"


# ---------------------------------------------------------------- helpers

def parseGuideName(name):
	"""Parse a `_guide.*` glyph name into base/include/exclude/color components."""
	if not name or not name.startswith("_guide."):
		return None
	colorSuffix = None
	basePart = name
	if ".c_" in name:
		basePart, colorSuffix = name.split(".c_", 1)
	parts = basePart.split(".")
	result = {"base": [], "include": [], "exclude": [], "color": colorSuffix}
	for part in parts[1:]:
		if part.startswith("-"):
			result["exclude"].append(part[1:])
		elif part.startswith("in_"):
			result["include"].append(part[3:])
		else:
			result["base"].append(part)
	return result


def buildGuideName(parsed):
	"""Build a `_guide.*` glyph name from parsed components."""
	parts = ["_guide"]
	parts.extend(parsed.get("base") or [])
	for inc in parsed.get("include") or []:
		parts.append("in_" + inc)
	for exc in parsed.get("exclude") or []:
		parts.append("-" + exc)
	name = ".".join(parts)
	if parsed.get("color"):
		name += ".c_" + parsed["color"]
	return name


def hexToNSColor(hexStr, alpha=1.0):
	if not hexStr or len(hexStr) < 6:
		return None
	try:
		r = int(hexStr[0:2], 16) / 255.0
		g = int(hexStr[2:4], 16) / 255.0
		b = int(hexStr[4:6], 16) / 255.0
		return NSColor.colorWithRed_green_blue_alpha_(r, g, b, alpha)
	except Exception:
		return None


def nsColorToHex(color):
	if color is None:
		return None
	rgb = color.colorUsingColorSpaceName_("NSCalibratedRGBColorSpace")
	if rgb is None:
		try:
			rgb = color.colorUsingColorSpace_(NSColor.genericRGBColor().colorSpace())
		except Exception:
			rgb = None
	if rgb is None:
		return None
	r = int(round(rgb.redComponent() * 255))
	g = int(round(rgb.greenComponent() * 255))
	b = int(round(rgb.blueComponent() * 255))
	return "%02X%02X%02X" % (max(0, min(255, r)), max(0, min(255, g)), max(0, min(255, b)))


def guideColorHex(font, colorSuffix, preferOpen=True):
	"""Read the appropriate Guide Color custom parameter and return a 6-char hex
	for either the open or closed path."""
	paramName = "Guide Color"
	if colorSuffix:
		candidate = "Guide Color:" + colorSuffix
		if candidate in font.customParameters:
			paramName = candidate
	if paramName not in font.customParameters:
		return None
	raw = font.customParameters[paramName]
	if not raw:
		return None
	raw = str(raw).strip()
	if "," not in raw and len(raw) >= 13:
		return raw[0:6] if preferOpen else raw[7:13]
	parts = [p.strip() for p in raw.split(",")]
	if preferOpen:
		return parts[0][:6]
	return parts[1][:6] if len(parts) > 1 else parts[0][:6]


def systemSymbolImage(name):
	"""Return an NSImage for an SF Symbol; nil on macOS < 11."""
	try:
		return NSImage.imageWithSystemSymbolName_accessibilityDescription_(name, None)
	except Exception:
		return None


# ---------------------------------------------------------------- tree nodes

class GuideGroupNode(object):
	__slots__ = ("name", "children", "expanded")

	def __init__(self, name):
		self.name = name
		self.children = []
		self.expanded = True


class GuideItemNode(object):
	__slots__ = ("glyphName", "displayName", "colorHex", "visible", "parsed", "group")

	def __init__(self, glyphName, displayName, colorHex, visible, parsed, group):
		self.glyphName = glyphName
		self.displayName = displayName
		self.colorHex = colorHex
		self.visible = visible
		self.parsed = parsed
		self.group = group


# ---------------------------------------------------------------- plugin

class ShowGuideSheetsPalette(PalettePlugin):

	@objc.python_method
	def settings(self):
		print("ShowGuideSheetsPalette: settings()")
		try:
			self.name = Glyphs.localize({
				"en": "Guide Sheets",
				"ja": "原稿用紙",
				"zh-Hant": "稿紙",
				"zh-Hans": "稿纸",
			})

			width = 240
			height = 280

			# Window+Group is the proven pattern (matches MasterSeriesCopy).
			self.paletteView = Window((width, height))
			self.paletteView.group = Group((0, 0, width, height))

			# Build NSOutlineView programmatically.
			outlineView = NSOutlineView.alloc().init()

			showCol = NSTableColumn.alloc().initWithIdentifier_(SHOW_COL_ID)
			showCol.setWidth_(28.0)
			showCol.setMinWidth_(28.0)
			showCol.setMaxWidth_(28.0)
			showCol.setEditable_(False)
			showCol.setResizingMask_(0)
			outlineView.addTableColumn_(showCol)

			nameCol = NSTableColumn.alloc().initWithIdentifier_(NAME_COL_ID)
			nameCol.setWidth_(180.0)
			nameCol.setMinWidth_(80.0)
			nameCol.setEditable_(False)
			outlineView.addTableColumn_(nameCol)

			outlineView.setOutlineTableColumn_(nameCol)
			outlineView.setHeaderView_(None)
			outlineView.setIndentationPerLevel_(14.0)
			outlineView.setRowHeight_(22.0)
			outlineView.setAllowsColumnReordering_(False)
			outlineView.setAllowsColumnResizing_(False)
			outlineView.setAllowsMultipleSelection_(False)
			outlineView.setAllowsEmptySelection_(True)
			outlineView.setUsesAlternatingRowBackgroundColors_(False)
			try:
				outlineView.setSelectionHighlightStyle_(NSTableViewSelectionHighlightStyleSourceList)
			except Exception:
				pass
			outlineView.setAutoresizesOutlineColumn_(False)
			outlineView.setFloatsGroupRows_(False)
			outlineView.setDataSource_(self)
			outlineView.setDelegate_(self)

			self.outlineView = outlineView

			# Wrap the outline view in vanilla.ScrollView so it autosizes inside the Group.
			self.paletteView.group.scroll = ScrollView(
				(0, 0, -0, -32),
				outlineView,
				hasHorizontalScroller=False,
				autohidesScrollers=True,
				drawsBackground=False,
			)

			self.paletteView.group.addButton = Button(
				(4, -26, 28, 22), "+",
				callback=self._addCallback, sizeStyle="small",
			)
			self.paletteView.group.removeButton = Button(
				(36, -26, 28, 22), "−",
				callback=self._removeCallback, sizeStyle="small",
			)

			self.dialog = self.paletteView.group.getNSView()

			# Tree state
			self._groups = []  # list of GuideGroupNode
			self._eyeButtonByName = {}  # glyphName -> NSButton (for incremental updates)
			self._suppressExpandSave = False

			# Load eye icons from SVGs bundled in Resources/.
			self._eyeShowImage = self._loadEyeIcon("show02_.svg")
			self._eyeHideImage = self._loadEyeIcon("hide02_.svg")
		except Exception:
			print("ShowGuideSheetsPalette settings() error:")
			print(traceback.format_exc())
			raise

	@objc.python_method
	def start(self):
		print("ShowGuideSheetsPalette: start()")
		try:
			Glyphs.addCallback(self.update, UPDATEINTERFACE)
		except Exception:
			print("ShowGuideSheetsPalette: addCallback failed")
			print(traceback.format_exc())
		try:
			self._menu = self._buildContextMenu()
			self.outlineView.setMenu_(self._menu)
			self.outlineView.setDoubleAction_("paletteDoubleClickAction:")
			self.outlineView.setTarget_(self)
		except Exception:
			print("ShowGuideSheetsPalette: NSOutlineView wiring failed")
			print(traceback.format_exc())
		try:
			self._refresh()
		except Exception:
			print("ShowGuideSheetsPalette: initial refresh failed")
			print(traceback.format_exc())

	@objc.python_method
	def __del__(self):
		try:
			Glyphs.removeCallback(self.update)
		except Exception:
			pass

	def minHeight(self):
		return 180

	def maxHeight(self):
		return 800

	@objc.python_method
	def update(self, sender):
		# Glyphs posts this on every mouse-drag event while editing: refresh once
		# for a burst of updates, after the mouse button is released.
		NSObject.cancelPreviousPerformRequestsWithTarget_selector_object_(
			self, "deferredRefresh:", None)
		self.performSelector_withObject_afterDelay_("deferredRefresh:", None, 0.0)

	def deferredRefresh_(self, sender):
		if NSEvent.pressedMouseButtons():
			self.performSelector_withObject_afterDelay_("deferredRefresh:", None, 0.25)
			return
		try:
			self._refresh(onlyIfChanged=True)
		except Exception:
			print(traceback.format_exc())

	# ---------------------------------------------------------------- font / userData

	@objc.python_method
	def _currentFont(self):
		try:
			return Glyphs.font
		except Exception:
			return None

	@objc.python_method
	def _readListUserData(self, font, key):
		if not font:
			return []
		try:
			raw = font.userData[key] if font.userData else None
		except Exception:
			raw = None
		if not raw:
			return []
		try:
			return list(raw)
		except Exception:
			return []

	@objc.python_method
	def _writeListUserData(self, font, key, values):
		if not font:
			return
		try:
			if values:
				font.userData[key] = list(sorted(values))
			else:
				if font.userData and key in font.userData:
					del font.userData[key]
		except Exception:
			print(traceback.format_exc())

	@objc.python_method
	def _hiddenSet(self, font):
		return set(self._readListUserData(font, HIDDEN_KEY))

	@objc.python_method
	def _saveHidden(self, font, hidden):
		self._writeListUserData(font, HIDDEN_KEY, list(hidden))

	@objc.python_method
	def _collapsedSet(self, font):
		return set(self._readListUserData(font, COLLAPSED_KEY))

	@objc.python_method
	def _saveCollapsed(self, font):
		collapsed = [g.name for g in self._groups if not g.expanded]
		self._writeListUserData(font, COLLAPSED_KEY, collapsed)

	@objc.python_method
	def _displayNameForGlyph(self, glyph):
		try:
			if glyph.userData:
				dn = glyph.userData[DISPLAYNAME_KEY]
				if dn:
					return str(dn)
		except Exception:
			pass
		return glyph.name

	@objc.python_method
	def _invalidateEditView(self, font):
		if not font:
			return
		try:
			tabs = font.tabs or []
		except Exception:
			tabs = []
		for tab in tabs:
			try:
				gv = tab.graphicView()
				if gv is not None:
					gv.setNeedsDisplay_(True)
			except Exception:
				try:
					gv = tab.graphicView
					if gv is not None:
						gv.setNeedsDisplay_(True)
				except Exception:
					pass

	# ---------------------------------------------------------------- refresh

	@objc.python_method
	def _refresh(self, onlyIfChanged=False):
		font = self._currentFont()
		groups = []

		if font is not None:
			hidden = self._hiddenSet(font)
			collapsed = self._collapsedSet(font)

			byGroup = {}
			for glyph in font.glyphs:
				name = glyph.name
				if not name or not name.startswith("_guide."):
					continue
				parsed = parseGuideName(name)
				if not parsed:
					continue
				groupKey = ".".join(parsed["base"]) if parsed["base"] else "any"
				display = self._displayNameForGlyph(glyph)
				color = guideColorHex(font, parsed["color"], preferOpen=True) or "1A99CC"
				node = GuideItemNode(
					glyphName=name,
					displayName=display,
					colorHex=color,
					visible=name not in hidden,
					parsed=parsed,
					group=groupKey,
				)
				if groupKey not in byGroup:
					g = GuideGroupNode(groupKey)
					g.expanded = groupKey not in collapsed
					byGroup[groupKey] = g
				byGroup[groupKey].children.append(node)

			for key in sorted(byGroup.keys()):
				g = byGroup[key]
				g.children.sort(key=lambda n: (n.displayName.lower(), n.glyphName))
				groups.append(g)

		# Interface updates rarely change the guides: keep the list (and its
		# row views) when nothing it shows has changed.
		signature = tuple(
			(g.name, g.expanded, tuple((n.glyphName, n.displayName, n.colorHex, n.visible)
			                           for n in g.children))
			for g in groups)
		if onlyIfChanged and signature == getattr(self, "_signature", None):
			return
		self._signature = signature
		self._groups = groups
		self._eyeButtonByName = {}

		try:
			self._suppressExpandSave = True
			self.outlineView.reloadData()
			# Restore expansion state.
			for g in self._groups:
				if g.expanded:
					self.outlineView.expandItem_(g)
				else:
					self.outlineView.collapseItem_(g)
		finally:
			self._suppressExpandSave = False

	# ---------------------------------------------------------------- NSOutlineView data source

	def outlineView_numberOfChildrenOfItem_(self, ov, item):
		try:
			if item is None:
				return len(self._groups)
			if isinstance(item, GuideGroupNode):
				return len(item.children)
		except Exception:
			print(traceback.format_exc())
		return 0

	def outlineView_isItemExpandable_(self, ov, item):
		return isinstance(item, GuideGroupNode) and len(item.children) > 0

	def outlineView_child_ofItem_(self, ov, index, item):
		try:
			if item is None:
				return self._groups[index]
			if isinstance(item, GuideGroupNode):
				return item.children[index]
		except Exception:
			print(traceback.format_exc())
		return None

	def outlineView_objectValueForTableColumn_byItem_(self, ov, column, item):
		# View-based outline view — return None and let the delegate provide the view.
		return None

	# ---------------------------------------------------------------- NSOutlineView delegate

	# Note: we deliberately do NOT implement `outlineView:isGroupItem:` —
	# returning YES would put the group row into Apple's cell-based "source
	# list group" rendering and bypass our view-based `viewForTableColumn`,
	# which results in a blank group row.

	def outlineView_shouldSelectItem_(self, ov, item):
		# Groups should not be selectable as items.
		return not isinstance(item, GuideGroupNode)

	def outlineView_viewForTableColumn_item_(self, ov, column, item):
		try:
			colId = str(column.identifier())
			if isinstance(item, GuideGroupNode):
				if colId == SHOW_COL_ID:
					return self._buildEmptyView()
				return self._buildGroupNameView(item)
			else:
				if colId == SHOW_COL_ID:
					return self._buildEyeButton(item)
				return self._buildItemNameView(item)
		except Exception:
			print(traceback.format_exc())
			return self._buildEmptyView()

	def outlineViewItemDidExpand_(self, notification):
		if self._suppressExpandSave:
			return
		try:
			info = notification.userInfo()
			item = info["NSObject"] if info else None
			if isinstance(item, GuideGroupNode):
				item.expanded = True
				self._saveCollapsed(self._currentFont())
		except Exception:
			print(traceback.format_exc())

	def outlineViewItemDidCollapse_(self, notification):
		if self._suppressExpandSave:
			return
		try:
			info = notification.userInfo()
			item = info["NSObject"] if info else None
			if isinstance(item, GuideGroupNode):
				item.expanded = False
				self._saveCollapsed(self._currentFont())
		except Exception:
			print(traceback.format_exc())

	# ---------------------------------------------------------------- view builders

	@objc.python_method
	def _buildEmptyView(self):
		return NSView.alloc().initWithFrame_(NSMakeRect(0, 0, 1, 1))

	@objc.python_method
	def _buildLabelView(self, text, bold=False, dim=False):
		"""Build a centred, plain (non-editable) text label inside a row cell."""
		cellW, cellH = 200.0, 22.0
		tfH = 16.0
		view = NSView.alloc().initWithFrame_(NSMakeRect(0, 0, cellW, cellH))
		tf = NSTextField.alloc().initWithFrame_(NSMakeRect(0, (cellH - tfH) / 2.0, cellW, tfH))
		tf.setStringValue_(text or "")
		tf.setBezeled_(False)
		tf.setDrawsBackground_(False)
		tf.setEditable_(False)
		tf.setSelectable_(False)
		if bold:
			tf.setFont_(NSFont.boldSystemFontOfSize_(11))
			try:
				tf.setTextColor_(NSColor.secondaryLabelColor())
			except Exception:
				pass
		else:
			tf.setFont_(NSFont.systemFontOfSize_(12))
			try:
				if dim:
					tf.setTextColor_(NSColor.tertiaryLabelColor())
				else:
					tf.setTextColor_(NSColor.labelColor())
			except Exception:
				pass
		tf.setAutoresizingMask_(NSViewWidthSizable)
		view.addSubview_(tf)
		return view

	@objc.python_method
	def _buildGroupNameView(self, group):
		return self._buildLabelView(group.name, bold=True)

	@objc.python_method
	def _buildItemNameView(self, item):
		return self._buildLabelView(item.displayName, bold=False, dim=not item.visible)

	@objc.python_method
	def _loadEyeIcon(self, filename):
		"""Load an SVG icon shipped in the bundle's Resources folder."""
		try:
			path = os.path.join(os.path.dirname(__file__), filename)
			if not os.path.isfile(path):
				return None
			img = NSImage.alloc().initWithContentsOfFile_(path)
			if img is None:
				return None
			# The SVG ships with a 500×500 viewBox. Pin the rendered size so the
			# NSButton's image-scaling logic has a sensible starting point.
			img.setSize_(NSMakeSize(16.0, 16.0))
			# Template image — adapts to dark mode and selection colour automatically.
			try:
				img.setTemplate_(True)
			except Exception:
				pass
			return img
		except Exception:
			print(traceback.format_exc())
			return None

	@objc.python_method
	def _buildEyeButton(self, item):
		# Cell view is showColumnWidth × rowHeight = 28 × 22. Centre a 18×18
		# image-only button inside it.
		cellW, cellH = 28.0, 22.0
		btnW, btnH = 18.0, 18.0
		view = NSView.alloc().initWithFrame_(NSMakeRect(0, 0, cellW, cellH))
		button = NSButton.alloc().initWithFrame_(NSMakeRect(
			(cellW - btnW) / 2.0,
			(cellH - btnH) / 2.0,
			btnW, btnH,
		))
		button.setBordered_(False)
		button.setButtonType_(NSMomentaryChangeButton)
		button.setTitle_("")
		# Keep the button centred if the row ever resizes.
		button.setAutoresizingMask_(
			NSViewMinXMargin | NSViewMaxXMargin | NSViewMinYMargin | NSViewMaxYMargin
		)
		# Identifier carries the glyph name so the action handler knows who clicked.
		try:
			button.setIdentifier_(item.glyphName)
		except Exception:
			pass

		showImg = getattr(self, "_eyeShowImage", None)
		hideImg = getattr(self, "_eyeHideImage", None)

		# Fallback ladder: bundled SVG → SF Symbol → text glyph.
		img = (showImg if item.visible else hideImg)
		if img is None:
			img = systemSymbolImage("eye" if item.visible else "eye.slash")

		if img is not None:
			button.setImage_(img)
			button.setImagePosition_(NSImageOnly)
			try:
				button.setImageScaling_(NSImageScaleProportionallyUpOrDown)
			except Exception:
				pass
			try:
				button.cell().setImageScaling_(NSImageScaleProportionallyUpOrDown)
			except Exception:
				pass
			try:
				button.cell().setImageAlignment_(NSImageAlignCenter)
			except Exception:
				pass
			try:
				button.setContentTintColor_(
					NSColor.labelColor() if item.visible else NSColor.tertiaryLabelColor()
				)
			except Exception:
				pass
		else:
			button.setTitle_("●" if item.visible else "○")
			try:
				button.setFont_(NSFont.systemFontOfSize_(13))
			except Exception:
				pass

		button.setTarget_(self)
		button.setAction_("eyeButtonClicked:")
		view.addSubview_(button)
		# Track the button for incremental updates.
		self._eyeButtonByName[item.glyphName] = button
		return view

	# ---------------------------------------------------------------- eye toggle

	def eyeButtonClicked_(self, sender):
		try:
			glyphName = str(sender.identifier() or "")
		except Exception:
			glyphName = ""
		if not glyphName:
			return
		font = self._currentFont()
		if not font:
			return
		hidden = self._hiddenSet(font)
		if glyphName in hidden:
			hidden.discard(glyphName)
			nowVisible = True
		else:
			hidden.add(glyphName)
			nowVisible = False
		self._saveHidden(font, hidden)
		self._invalidateEditView(font)
		# Update the in-memory node and the button image, then reload that row.
		for g in self._groups:
			for node in g.children:
				if node.glyphName == glyphName:
					node.visible = nowVisible
					try:
						row = self.outlineView.rowForItem_(node)
						if row >= 0:
							rows = NSIndexSet.indexSetWithIndex_(row)
							cols = NSIndexSet.indexSetWithIndexesInRange_((0, self.outlineView.numberOfColumns()))
							self.outlineView.reloadDataForRowIndexes_columnIndexes_(rows, cols)
					except Exception:
						print(traceback.format_exc())
					return

	# ---------------------------------------------------------------- click helpers

	@objc.python_method
	def _clickedItemNode(self):
		try:
			row = self.outlineView.clickedRow()
			if row is None or row < 0:
				row = self.outlineView.selectedRow()
			if row is None or row < 0:
				return None
			item = self.outlineView.itemAtRow_(row)
			if isinstance(item, GuideItemNode):
				return item
		except Exception:
			print(traceback.format_exc())
		return None

	@objc.python_method
	def _selectedItemNode(self):
		try:
			row = self.outlineView.selectedRow()
			if row is None or row < 0:
				return None
			item = self.outlineView.itemAtRow_(row)
			if isinstance(item, GuideItemNode):
				return item
		except Exception:
			pass
		return None

	# ---------------------------------------------------------------- + / -

	@objc.python_method
	def _addCallback(self, sender):
		font = self._currentFont()
		if not font:
			return
		result = self._showAddDialog()
		if not result:
			return
		parsed = {
			"base": [s.strip() for s in result["base"].split(",") if s.strip()],
			"include": [s.strip() for s in result["include"].split(",") if s.strip()],
			"exclude": [s.strip() for s in result["exclude"].split(",") if s.strip()],
			"color": result["color"].strip() or None,
		}
		glyphName = buildGuideName(parsed)
		if font.glyphs[glyphName] is not None:
			self._showAlert("Already exists", "A guide glyph named '%s' already exists." % glyphName)
			return
		newGlyph = GSGlyph(glyphName)
		font.glyphs.append(newGlyph)
		display = result.get("displayName", "").strip()
		if display:
			try:
				newGlyph.userData[DISPLAYNAME_KEY] = display
			except Exception:
				print(traceback.format_exc())

		# When an edit tab is open, splice the new guide in before the active
		# glyph so it is visible immediately. When in font view, just leave
		# the glyph created in the font without disrupting the current view.
		editTab = self._activeEditTab(font)
		if editTab is not None:
			self._insertGuideInTab(font, editTab, glyphName)

		self._invalidateEditView(font)
		self._refresh()

	@objc.python_method
	def _removeCallback(self, sender):
		node = self._selectedItemNode()
		if not node:
			return
		font = self._currentFont()
		if not font:
			return
		if not self._confirm("Delete guide", "Delete glyph '%s'? This cannot be undone." % node.glyphName):
			return
		self._deleteGuide(font, node.glyphName)

	@objc.python_method
	def _deleteGuide(self, font, glyphName):
		try:
			del font.glyphs[glyphName]
		except Exception:
			try:
				glyph = font.glyphs[glyphName]
				if glyph is not None:
					font.removeGlyph_(glyph)
			except Exception:
				print(traceback.format_exc())
		hidden = self._hiddenSet(font)
		hidden.discard(glyphName)
		self._saveHidden(font, hidden)
		self._invalidateEditView(font)
		self._refresh()

	# ---------------------------------------------------------------- tab insertion

	@objc.python_method
	def _insertGuideInTab(self, font, tab, glyphName):
		"""Insert the given guide glyph's layer into the tab at the current
		cursor position (i.e. immediately before the glyph the user is
		editing). Returns True on success."""
		if font is None or tab is None:
			return False
		guide = font.glyphs[glyphName]
		if guide is None:
			return False

		# Resolve the right master for this tab.
		try:
			masterIdx = int(tab.masterIndex)
		except Exception:
			masterIdx = 0
		try:
			masters = list(font.masters or [])
		except Exception:
			masters = []
		masterId = None
		if 0 <= masterIdx < len(masters):
			masterId = masters[masterIdx].id
		elif masters:
			masterId = masters[0].id
		if not masterId:
			return False

		guideLayer = guide.layers[masterId]
		if guideLayer is None:
			return False

		try:
			currentLayers = list(tab.layers)
		except Exception:
			print(traceback.format_exc())
			return False

		# Prefer layersCursor (index in tab.layers); fall back to textCursor.
		cursor = None
		try:
			cursor = int(tab.layersCursor)
		except Exception:
			try:
				cursor = int(tab.textCursor)
			except Exception:
				cursor = None
		if cursor is None:
			cursor = len(currentLayers)
		cursor = max(0, min(cursor, len(currentLayers)))

		try:
			currentLayers.insert(cursor, guideLayer)
			tab.layers = currentLayers
		except Exception:
			print(traceback.format_exc())
			return False

		# Move the cursor past the inserted guide so the user keeps editing
		# the same glyph they were on.
		try:
			tab.layersCursor = cursor + 1
		except Exception:
			try:
				tab.textCursor = cursor + 1
			except Exception:
				pass
		return True

	# ---------------------------------------------------------------- double-click

	def paletteDoubleClickAction_(self, sender):
		# Skip if click was on the eye column.
		try:
			if self.outlineView.clickedColumn() == 0:
				return
		except Exception:
			pass
		node = self._clickedItemNode()
		if not node:
			return
		font = self._currentFont()
		if not font:
			return
		editTab = self._activeEditTab(font)
		if editTab is not None:
			if self._insertGuideInTab(font, editTab, node.glyphName):
				return
			# Fallback if layer-insert fails for some reason.
			try:
				editTab.text = (editTab.text or "") + "/" + node.glyphName + " "
				return
			except Exception:
				print(traceback.format_exc())
		try:
			font.newTab("/" + node.glyphName + " ")
		except Exception:
			print(traceback.format_exc())

	@objc.python_method
	def _activeEditTab(self, font):
		try:
			doc = Glyphs.currentDocument
			if doc is None:
				return None
			wc = doc.windowController()
			if wc is None:
				return None
			vc = wc.activeEditViewController()
			if vc is None:
				return None
			if isinstance(vc, GSEditViewController):
				return font.currentTab
			return font.currentTab
		except Exception:
			return None

	# ---------------------------------------------------------------- right-click

	@objc.python_method
	def _buildContextMenu(self):
		menu = NSMenu.alloc().init()
		menu.setAutoenablesItems_(False)
		entries = [
			(Glyphs.localize({"en": "Edit Display Name…", "ja": "表示名を編集…"}), "menuEditDisplayName:"),
			(Glyphs.localize({"en": "Edit Conditions…", "ja": "表示条件を編集…"}), "menuEditConditions:"),
			(Glyphs.localize({"en": "Edit Color…", "ja": "ガイドカラーを編集…"}), "menuEditColor:"),
			(None, None),
			(Glyphs.localize({"en": "Open in Edit View", "ja": "編集ビューで開く"}), "menuOpenInTab:"),
			(Glyphs.localize({"en": "Delete", "ja": "削除"}), "menuDelete:"),
		]
		for title, action in entries:
			if title is None:
				menu.addItem_(NSMenuItem.separatorItem())
				continue
			item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(title, action, "")
			item.setTarget_(self)
			menu.addItem_(item)
		return menu

	def menuEditDisplayName_(self, sender):
		node = self._clickedItemNode()
		if not node:
			return
		font = self._currentFont()
		if not font:
			return
		glyph = font.glyphs[node.glyphName]
		if glyph is None:
			return
		current = ""
		try:
			if glyph.userData:
				current = glyph.userData[DISPLAYNAME_KEY] or ""
		except Exception:
			pass
		newName = self._promptText(
			Glyphs.localize({"en": "Edit Display Name", "ja": "表示名を編集"}),
			Glyphs.localize({"en": "Custom display name (empty to use glyph name):", "ja": "表示名（空欄でグリフ名を使用）："}),
			current,
		)
		if newName is None:
			return
		newName = newName.strip()
		try:
			if newName:
				glyph.userData[DISPLAYNAME_KEY] = newName
			else:
				if glyph.userData and DISPLAYNAME_KEY in glyph.userData:
					del glyph.userData[DISPLAYNAME_KEY]
		except Exception:
			print(traceback.format_exc())
		self._refresh()

	def menuEditConditions_(self, sender):
		node = self._clickedItemNode()
		if not node:
			return
		font = self._currentFont()
		if not font:
			return
		glyph = font.glyphs[node.glyphName]
		if glyph is None:
			return
		parsed = parseGuideName(glyph.name) or {"base": [], "include": [], "exclude": [], "color": None}
		result = self._showConditionsDialog(parsed)
		if not result:
			return
		newParsed = {
			"base": [s.strip() for s in result["base"].split(",") if s.strip()],
			"include": [s.strip() for s in result["include"].split(",") if s.strip()],
			"exclude": [s.strip() for s in result["exclude"].split(",") if s.strip()],
			"color": result["color"].strip() or None,
		}
		newName = buildGuideName(newParsed)
		oldName = glyph.name
		if newName == oldName:
			return
		conflict = font.glyphs[newName]
		if conflict is not None and conflict is not glyph:
			self._showAlert("Conflict", "A guide named '%s' already exists." % newName)
			return
		try:
			glyph.name = newName
		except Exception:
			print(traceback.format_exc())
			return
		hidden = self._hiddenSet(font)
		if oldName in hidden:
			hidden.discard(oldName)
			hidden.add(newName)
			self._saveHidden(font, hidden)
		self._invalidateEditView(font)
		self._refresh()

	def menuEditColor_(self, sender):
		node = self._clickedItemNode()
		if not node:
			return
		font = self._currentFont()
		if not font:
			return
		glyph = font.glyphs[node.glyphName]
		if glyph is None:
			return
		parsed = parseGuideName(glyph.name) or {"base": [], "include": [], "exclude": [], "color": None}
		colorSuffix = parsed.get("color")
		oldName = glyph.name

		if not colorSuffix:
			suffix = self._promptText(
				Glyphs.localize({"en": "Color Group", "ja": "カラーグループ"}),
				Glyphs.localize({
					"en": "This guide has no color suffix. Enter a name (e.g. red, main):",
					"ja": "このガイドにはカラーサフィックスがありません。名前を入力してください（例: red, main）：",
				}),
				"main",
			)
			if not suffix or not suffix.strip():
				return
			colorSuffix = suffix.strip()
			parsed["color"] = colorSuffix
			newName = buildGuideName(parsed)
			conflict = font.glyphs[newName]
			if conflict is not None and conflict is not glyph:
				self._showAlert("Conflict", "A guide named '%s' already exists." % newName)
				return
			try:
				glyph.name = newName
			except Exception:
				print(traceback.format_exc())
				return
			hidden = self._hiddenSet(font)
			if oldName in hidden:
				hidden.discard(oldName)
				hidden.add(newName)
				self._saveHidden(font, hidden)

		existingOpen = guideColorHex(font, colorSuffix, preferOpen=True) or "1A99CC"
		existingClosed = guideColorHex(font, colorSuffix, preferOpen=False) or existingOpen
		picked = self._showColorDialog(existingOpen, existingClosed)
		if picked is None:
			return
		openHex, closedHex = picked
		value = openHex if openHex == closedHex else (openHex + "," + closedHex)
		try:
			font.customParameters["Guide Color:" + colorSuffix] = value
		except Exception:
			print(traceback.format_exc())
		self._invalidateEditView(font)
		self._refresh()

	def menuOpenInTab_(self, sender):
		node = self._clickedItemNode()
		if not node:
			return
		font = self._currentFont()
		if not font:
			return
		try:
			font.newTab("/" + node.glyphName)
		except Exception:
			print(traceback.format_exc())

	def menuDelete_(self, sender):
		node = self._clickedItemNode()
		if not node:
			return
		font = self._currentFont()
		if not font:
			return
		if not self._confirm("Delete guide", "Delete glyph '%s'? This cannot be undone." % node.glyphName):
			return
		self._deleteGuide(font, node.glyphName)

	# ---------------------------------------------------------------- dialogs

	@objc.python_method
	def _showAlert(self, title, message):
		alert = NSAlert.alloc().init()
		alert.setMessageText_(title)
		alert.setInformativeText_(message)
		alert.runModal()

	@objc.python_method
	def _confirm(self, title, message):
		alert = NSAlert.alloc().init()
		alert.setMessageText_(title)
		alert.setInformativeText_(message)
		alert.addButtonWithTitle_(Glyphs.localize({"en": "Delete", "ja": "削除"}))
		alert.addButtonWithTitle_(Glyphs.localize({"en": "Cancel", "ja": "キャンセル"}))
		alert.setAlertStyle_(NSWarningAlertStyle)
		return alert.runModal() == NSAlertFirstButtonReturn

	@objc.python_method
	def _promptText(self, title, prompt, default=""):
		alert = NSAlert.alloc().init()
		alert.setMessageText_(title)
		alert.setInformativeText_(prompt)
		alert.addButtonWithTitle_("OK")
		alert.addButtonWithTitle_(Glyphs.localize({"en": "Cancel", "ja": "キャンセル"}))
		tf = NSTextField.alloc().initWithFrame_(NSMakeRect(0, 0, 260, 24))
		tf.setStringValue_(default or "")
		alert.setAccessoryView_(tf)
		response = alert.runModal()
		if response != NSAlertFirstButtonReturn:
			return None
		return str(tf.stringValue() or "")

	@objc.python_method
	def _showAddDialog(self):
		alert = NSAlert.alloc().init()
		alert.setMessageText_(Glyphs.localize({"en": "New Guide Sheet", "ja": "新しい原稿用紙"}))
		alert.setInformativeText_(Glyphs.localize({
			"en": "Define conditions and an optional display name.",
			"ja": "表示条件と任意の表示名を入力してください。",
		}))
		alert.addButtonWithTitle_(Glyphs.localize({"en": "Add", "ja": "追加"}))
		alert.addButtonWithTitle_(Glyphs.localize({"en": "Cancel", "ja": "キャンセル"}))
		form = self._buildConditionsForm({"base": [], "include": [], "exclude": [], "color": None}, includeDisplay=True)
		alert.setAccessoryView_(form["view"])
		if alert.runModal() != NSAlertFirstButtonReturn:
			return None
		return {
			"displayName": str(form["displayName"].stringValue() or ""),
			"base": str(form["base"].stringValue() or ""),
			"include": str(form["include"].stringValue() or ""),
			"exclude": str(form["exclude"].stringValue() or ""),
			"color": str(form["color"].stringValue() or ""),
		}

	@objc.python_method
	def _showConditionsDialog(self, parsed):
		alert = NSAlert.alloc().init()
		alert.setMessageText_(Glyphs.localize({"en": "Edit Conditions", "ja": "表示条件を編集"}))
		alert.setInformativeText_(Glyphs.localize({
			"en": "This will rename the underlying guide glyph.",
			"ja": "ガイドグリフがリネームされます。",
		}))
		alert.addButtonWithTitle_("OK")
		alert.addButtonWithTitle_(Glyphs.localize({"en": "Cancel", "ja": "キャンセル"}))
		form = self._buildConditionsForm(parsed, includeDisplay=False)
		alert.setAccessoryView_(form["view"])
		if alert.runModal() != NSAlertFirstButtonReturn:
			return None
		return {
			"base": str(form["base"].stringValue() or ""),
			"include": str(form["include"].stringValue() or ""),
			"exclude": str(form["exclude"].stringValue() or ""),
			"color": str(form["color"].stringValue() or ""),
		}

	@objc.python_method
	def _buildConditionsForm(self, parsed, includeDisplay=True):
		rows = []
		if includeDisplay:
			rows.append((Glyphs.localize({"en": "Display name (optional):", "ja": "表示名（任意）："}), "displayName", ""))
		rows.append((
			Glyphs.localize({"en": "Base (script/category, comma-separated):", "ja": "基本要素（script/category, カンマ区切り）："}),
			"base", ", ".join(parsed.get("base") or []),
		))
		rows.append((
			Glyphs.localize({"en": "Include (in_*, comma-separated):", "ja": "包含（in_*, カンマ区切り）："}),
			"include", ", ".join(parsed.get("include") or []),
		))
		rows.append((
			Glyphs.localize({"en": "Exclude (-*, comma-separated):", "ja": "除外（-*, カンマ区切り）："}),
			"exclude", ", ".join(parsed.get("exclude") or []),
		))
		rows.append((
			Glyphs.localize({"en": "Color suffix (.c_*, optional):", "ja": "カラーサフィックス（.c_*, 任意）："}),
			"color", parsed.get("color") or "",
		))

		rowH = 44
		width = 340
		totalH = rowH * len(rows)
		view = NSView.alloc().initWithFrame_(NSMakeRect(0, 0, width, totalH))
		fields = {"view": view}
		for i, (labelText, key, default) in enumerate(rows):
			y = totalH - rowH * (i + 1)
			label = NSTextField.alloc().initWithFrame_(NSMakeRect(0, y + 24, width, 16))
			label.setStringValue_(labelText)
			label.setBezeled_(False)
			label.setDrawsBackground_(False)
			label.setEditable_(False)
			label.setSelectable_(False)
			label.setFont_(NSFont.systemFontOfSize_(11))
			view.addSubview_(label)
			tf = NSTextField.alloc().initWithFrame_(NSMakeRect(0, y, width, 22))
			tf.setStringValue_(default)
			view.addSubview_(tf)
			fields[key] = tf
		return fields

	@objc.python_method
	def _showColorDialog(self, openHex, closedHex):
		alert = NSAlert.alloc().init()
		alert.setMessageText_(Glyphs.localize({"en": "Edit Guide Color", "ja": "ガイドカラーを編集"}))
		alert.setInformativeText_(Glyphs.localize({
			"en": "Pick colors for open and closed paths.",
			"ja": "開放パスと閉鎖パスの色を選択してください。",
		}))
		alert.addButtonWithTitle_("OK")
		alert.addButtonWithTitle_(Glyphs.localize({"en": "Cancel", "ja": "キャンセル"}))

		view = NSView.alloc().initWithFrame_(NSMakeRect(0, 0, 280, 80))

		labelOpen = NSTextField.alloc().initWithFrame_(NSMakeRect(0, 50, 120, 18))
		labelOpen.setStringValue_(Glyphs.localize({"en": "Open path:", "ja": "開放パス："}))
		labelOpen.setBezeled_(False)
		labelOpen.setDrawsBackground_(False)
		labelOpen.setEditable_(False)
		labelOpen.setSelectable_(False)
		view.addSubview_(labelOpen)

		wellOpen = NSColorWell.alloc().initWithFrame_(NSMakeRect(130, 46, 60, 26))
		c = hexToNSColor(openHex)
		if c:
			wellOpen.setColor_(c)
		view.addSubview_(wellOpen)

		labelClosed = NSTextField.alloc().initWithFrame_(NSMakeRect(0, 12, 120, 18))
		labelClosed.setStringValue_(Glyphs.localize({"en": "Closed path:", "ja": "閉鎖パス："}))
		labelClosed.setBezeled_(False)
		labelClosed.setDrawsBackground_(False)
		labelClosed.setEditable_(False)
		labelClosed.setSelectable_(False)
		view.addSubview_(labelClosed)

		wellClosed = NSColorWell.alloc().initWithFrame_(NSMakeRect(130, 8, 60, 26))
		c = hexToNSColor(closedHex)
		if c:
			wellClosed.setColor_(c)
		view.addSubview_(wellClosed)

		alert.setAccessoryView_(view)
		if alert.runModal() != NSAlertFirstButtonReturn:
			return None
		return (
			nsColorToHex(wellOpen.color()) or openHex,
			nsColorToHex(wellClosed.color()) or closedHex,
		)

	@objc.python_method
	def __file__(self):
		return __file__
