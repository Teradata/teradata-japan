# Teradata SQL Quiz

## SQL Quiz の始め方

1. [00_setup.ipynb](./00_setup.ipynb) を実行してください。その際に、お使いの環境に合わせて接続情報を変更指定ください。規定の値は[ClearScape Analytics Experience](https://clearscape.teradata.com) (無料のお試し環境) を想定したものになっています。
1. 上記のノートブックを実行すると、`_connect-info.json` というファイルに接続情報が保存されます。クイズのノートブックで参照するのでこれはそのままにしておいてください。
1. その他のお好きなノートブックを開き、一番上の `# このセルはそのまま実行して ...` から始まるセルを実行してください。
1. 各問題セルの下に `%%tdquiz` から始まるセルがあります。そこにクエリを打ち込んでセルを実行してください。すると、クエリの結果が出力されます（現バージョンでは正誤判定は行いません）。
1. 問題文の下の `▶ Hint` や `▶ Answer` をクリックするとヒントや想定解の１つが表示されます。
1. `en-` から始まるノートブックは問題文を英語にしたものです。ただしデータは日本語を含みます。


## 問題で使用するデータ

**TeraShirt データベース**

<image src="./images/Diagram_TeraShirt.png" width="400">

**facilities データベース**

<image src="./images/Diagram_facilities.png" width="400">

**japan データベース**

<image src="./images/Diagram_japan.png" width="400">


### Enjoy SQL!
