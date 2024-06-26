# Teradata Japan

このレポジトリでは、teradataデータベースの使い方や各種分析手法を紹介しています。
データベースの接続方法やクエリの書き方、統計分析や機械学習など、具体的な実装方法を交えて示すようにしています。

特別に断らない限り、コードやノートブックは [ClearScape Analytics Experience](https://clearscape.teradata.com) (無料のお試し環境) でそのまま動作するように書かれています（一部、同環境では実行できないものもありますが、極力手順がわかりやすくなるように配慮しています）。
無料でアカウント作成して利用できる環境ですので、ぜひ実際に触ってみて、teradata の面白さを体感してください。

## コンテンツ紹介

- [Tutorial](./tutorial/): Teradataの基本的な使い方を紹介しています。インターフェイス言語には主にPythonを採用しています。
- [SQL Quiz](./sqlquiz): SQLの練習問題を解くことができます。一般的なクエリからTeradata独自の構文まで幅広いトピックをカバーしています。

## ClearScape Analytics Experience (お試し環境) の始め方

### アカウント作成、ログイン

1. [ClearScape Analytics Experience](https://clearscape.teradata.com) を開く
2. "CREATE ACCOUNT" ボタンをクリック
3. Emailなどの必要事項を記入して "Get Started" をクリック
4. しばらくすると案内メールが届きます。メールに記載されたリンクを開く
5. パスワードを記入し、"SET PASSWORD" をクリック
6. [ClearScape Analytics Experience](https://clearscape.teradata.com/sign-in) を開き、Emailとパスワードでログイン

### 環境作成、Jupyterを起動

1. "CREATE ENVIRONMENT" をクリック
2. 環境名 (任意)、接続パスワード（任意）、Region（どこでも可だか、場合によっては自分の住んでいる地域が良い場合も）を設定
3. 数分で自分専用のお試し環境が立ち上がる
4. 使いたい環境を選択し、"RUN DEMOS USING JUPYTER" をクリック
5. Jupyter Lab が開きます。

### このレポジトリのノートブックを取得

1. "Launcher" タブを開き、"Terminal" をクリック
2. 開いたターミナルで、`git clone https://github.com/Teradata/teradata-japan.git` と打ち込み（またはコピーし）、Enter
3. 数秒で、"teradata-japan" フォルダが取り込まれます（フォルダ一覧が更新されない場合は更新ボタンを押す）

### ノートブックを実行

1. "teradata-japan" フォルダ以下に含まれるお好きなノートブック (.ipynb) ファイルを開く
2. 実行時には、先に設定した接続パスワード（ログインパスワードではないことに注意）の記入が必要になります



