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

<image src="./images/Diagram_TeraShirt.png" width="600">

**facilities データベース**

<image src="./images/Diagram_facilities.png" width="500">

**japan データベース**

<image src="./images/Diagram_japan.png" width="600">


### Enjoy SQL!


## 開発者向け

### 問題を編集・追加する

- 問題は[questions](./questions) ディレクトリ直下に .toml ファイルで設定します。
- 必須の要素は `title` `content` `judgement.query`, 任意の要素は `hint` です。その他の要素は使用していません。
- 問題を追加したり削除するには、[questions/_questions.csv](./questions/_questions.csv) を編集してください。また、順序を変えると問題の並びが変化します。
- 問題のカテゴリを追加・削除するには、 [questions/_categories.csv](questions/_categories.csv) を編集します。ノートブックはカテゴリ別に作成されます。
- 問題が作成できたら、[prep/11_generate-notebooks.ipynb](prep/11_generate-notebooks.ipynb) を実行すると、ノートブックに反映されます。この結果をコミットしてください。

### データを編集する

- データは、[data](./data) ディレクトリ以下に配置します。
- 保存場所のルールは `./data/{databasename}/{tablename}` です。
- `./data/{databasename}/ddl.toml` はデータベースの設定です。基本的には `perm_size` だけ指定すれば十分です。
- `./data/{databasename}/{tablename}/ddl.toml` はテーブルの設定です。列タイプやインデックスについて指定します。
- `./data/{databasename}/{tablename}/data.csv` はデータの中身です（ヘッダ付き）。
- `tdquiz.setup_tdquiz` を実行する自動的にこれらの定義を用いてデータベースとテーブルを作成するようになっています。
- [prep](./prep) ディレクトリにある `0`から始まるノートブックは、現在使用しているテーブルの CSVファイルを生成するものです。
