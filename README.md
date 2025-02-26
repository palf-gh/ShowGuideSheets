# Show Guide Sheets | 稿紙

Glyphs.app plug-in for displaying guide sheets for the glyph you are editing. This can be helpful especially for CJK glyphs editing.
You can create different guide sheets for different scripts. Each master may have different ones.
After installation, turn it on or off by choosing *View > Show Guide Sheets* (zh-Hant: 稿紙, ja: 原稿用紙)

這是一個 Glyphs 外掛程式，可在字符編輯畫面中顯示背景的稿紙，非常適合 CJK 文字編輯時定義字身框、字面框，以及各種編輯參考用框線。
每個主板的稿紙是分開的，即使是多主板編輯時，也能輕易管理不同的框線設定。
另外，不同語系的稿紙也可以分開定義。這表示漢字、假名、注音符號、韓文都可以各自有不同的稿紙背景。
在安裝外掛程式後，別忘記點選 顯示 > 顯示稿紙 (en: *Show Guide Sheets*) 打開它。

これは Glyphs のプラグインで、グリフの編集ビューの背景に原稿用紙（自由にデザインできるのであえて方眼紙と呼ばない）を表示することができます。
和文など CJK の文字デザインでは仮想ボディや字面など、デザインに必要なガイドが多岐にあるため、役に立つと思います。
マスターごとに違うデザインにすることもできるし、文字体系ごとに違う原稿用紙を用意することも可能。
インストールして、メニューの 表示 > 原稿用紙を表示 でオンにしてください。

![ShowGuideSheets](ShowGuideSheets.png)



## How to use | 使用方式 | 使い方

### English
1. Create a new glyph to make your own guide sheet. The glyph name should be `_guide.XXX`, where *XXX* is the script name or category. e.g. *_guide.han* (Chinese characters), *_guide.kana* (Kana), *_guide.bopomofo* (Bopomofo), *_guide.hangul* (Hangul), *_guide.Punctuation* (punctuation marks). You can combine script and category using dots, e.g. *_guide.han.Punctuation* (Chinese punctuation marks). Also `_guide.any` works for all characters (though less useful).
2. Add text notes by annotation tool if you need.
3. Now you can see the guide in the background when you edit glyphs. (It will not display anything if the zoom of the current tab is below 250px.)
4. Nodes which on the paths of guides will be highlighted. (It works when the zoom more than 400px)


### 繁體中文
1. 建立新字符來設計你的稿紙。字符名稱必須是 `_guide.XXX`，其中 *XXX* 表示文字語系或分類，例如 *_guide.han* (漢字), *_guide.kana* (假名), *_guide.hangul* (韓文), *_guide.Punctuation* (標點符號)。可用點號組合文字語系與分類，例如 *_guide.han.Punctuation* (漢字標點符號)。也可建立 `_guide.any` 適用於所有文字（但實用性較低）。
2. 若需要加上文字說明，可以用「註記」工具在適當位置加註文字。
3. 這樣在編輯文字時，就會看到背景出現稿紙了。（注意編輯面板必須大於 250px 時才會顯示。）
4. 當控制點接觸稿紙上的線條，會被凸顯顯示。（注意編輯面板必須大於 400px 時才會顯示。）


### 日本語　
1. まずは原稿用紙のグリフを作成してください。グリフ名は `_guide.XXX` で、*XXX* は文字体系またはカテゴリを指定してください。たとえば *_guide.han* (漢字), *_guide.kana* (仮名), *_guide.hangul* (ハングル), *_guide.Punctuation* (句読点)。文字体系とカテゴリを同時に指定することもできます。たとえば *_guide.han.Punctuation* (漢字の句読点)。また、 `_guide.any` はあらゆる文字に適用します（逆に使えないけど）。
2. メモ記述を入れたい場合は、注釈ツールでテキストをつけてください。
3. 編集ビューで該当文字体系のグリフを編集する場合、背景に原稿用紙が表示されます。（ズームが 250 以下だと表示されません。）
4. ガイドのパスの上に乗せたポイントはハイライトされます。（ズームが 400 以下だと表示されません。）



## Custom Parameter | 自訂參數 | カスタムパラメータ

You can change the color of guide lines. Just set the font custom parameter `Guide Color` in Hex color code, e.g. FF0000 means red lines.
Or you can set two color codes, e.g. FF0000,00FF00. The second one will be used for closed paths of your guide sheet.
If you create a parameter like `Guide Color:XXX`, guide glyphs ending with `.c_XXX` suffix will use this color setting.
You can also make dashed lines by creating `Line Style` parameter with values like "solid" or "dotted".
Similarly, you can specify two styles separated by comma, e.g. "solid,dotted" for open/closed paths.
`Line Style:XXX` parameters will apply to guide glyphs ending with `.c_XXX` suffix.

想要更改稿紙線條顏色，可以在字型資訊視窗中設定字型的自訂參數。名稱為 `Guide Color` ，請設定 6 位數的十六進位色碼。例如 FF0000 表示紅色。
或是您可指定兩種顏色，像是 FF0000,00FF00 這樣，此時第二組顏色會被套用在封閉路徑上（開放路徑與封閉路徑顯示成不同顏色）。
若建立 `Guide Color:XXX` 參數，則名稱結尾為 `.c_XXX` 的稿紙字符會套用此顏色設定。
另外，可透過 `Line Style` 參數設定線條為實線（solid）或虛線（dotted），例如設定為 "dotted" 即可讓稿紙線條變成虛線。
也可以像顏色設定一樣用逗號分隔兩種樣式，例如 "solid,dotted" 分別套用至開放與封閉路徑。
`Line Style:XXX` 參數會套用至名稱結尾為 `.c_XXX` 的稿紙字符。

ガイドの色は変更できます。フォントパラメータ `Guide Color` を作って、6 桁の十六進数のカラーコードを指定してください。たとえば FF0000 は赤です。
FF0000,00FF00 のように二種類の色を指定することができます。この場合、2個目の色はに閉じたパスに適用されます。（つまり開かれたパスと閉じたパスを違う色で表示することが可能です。）
`Guide Color:XXX` というパラメーターを作った場合、原稿用紙のグリフ名の末尾に `.c_XXX` というサフィックスがついているものの色を別途設定できます。*XXX*は任意の名称です。
また、ガイドの線を点線に変更することができます。フォントパラメータ `Line Style` を作って、solid また dotted を指定してください。
色設定と同様に、閉じたパスと開かれたパスを別々に設定することも可能です。
`Line Style:XXX` というパラメーターを作った場合、こちらも色設定と同様、原稿用紙のグリフ名の末尾に `.c_XXX` というサフィックスがついているものの線のスタイルを別途設定できます。


## Requirements

The plug-in works both in Glyphs 2 and Glyphs 3. I can only test it in latest app, and perhaps it crashs on earlier versions.

此外掛程式適用於 Glyphs 2 與 Glyphs 3，但只在目前最新版本測試過。

このプラグインは Glyphs 2 と Glyphs 3 に対応しています。ただし最新バージョンでしかテストしていません。



## License

Copyright 2021 But Ko (@buttaiwan).
Modified by Palf.
Based on sample code by Georg Seifert (@schriftgestalt).

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

http://www.apache.org/licenses/LICENSE-2.0

See the License file included in this repository for further details.
