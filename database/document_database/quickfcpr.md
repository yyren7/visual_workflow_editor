Quick-FCP

目次
Robot
wait
set motor
move origin
moveL
moveP
wait input
set output
set output during
set output until
robot io
robot position
stop robot upon
IO
connect external io
wait external io input
set external io output
set external io output during
set external io output until
external io
set external io output upon
Control
loop
return
wait timer
wait ready
wait run
Logic
if
start thread
create event
wait block
set flag
logic flag
logic custom flag
logic block
logic negate
logic compare
logic operation
set flag upon
Math
set number
math number
math custom number
math arithmetic
set number upon
Error
raise error
raise error upon
Pallet
set palet
move next pallet
reset pallet
Camera
connect camera
run camera wait
run camera
wait camera
PLC
connect plc
plc bit
plc word
set plc bit
set plc bit during
set plc bit until
set plc word
Function
define function
call function

ブロック説明
Robot
wait
命令を送信するロボットを選択する

入力変数

変数名 名称 形式 有効範囲 初期値 内容
robotName ロボット名 閲覧専用 開発済みのロボット 6 種類

1. Dobot MG400
2. Fairino FR
3. Hitbot Z ARM
4. YAMAHA Scara
5. IAI Tabletop
6. ***
7. ***
   "Setting"サイドバーで選択したロボット名 Robot カテゴリのブロック命令を送るためのロボット名
   使用例

"moveL"ブロックを参照して下さい

使用上の注意

・フローの先頭にのみ配置できます
・同一ワークスペースに 2 つ以上配置すると意図しない動作となる場合があります

set motor
ロボットのサーボモータ電源を操作する

入力変数

変数名 名称 形式 有効範囲 初期値 内容
motorStatus サーボモータ操作 プルダウン - ON:電源起動

- OFF:電源停止
  ON サーボモータ電源の操作方法
  使用例

"move"ブロックを参照して下さい

使用上の注意

"move"ブロックを使用する前に配置して下さい

move origin
ロボットを原点復帰する

入力変数

なし

使用例
"IAI 3 軸テーブルトップ"を原点復帰させ、"Home"位置に移動させます

使用上の注意

・インクリメント型のエンコーダーを備えたロボットにのみ必要となります
・Dobot MG400、Fairino FR、Hitbot Z ARM には不要です

moveL
ロボットを全軸絶対直線移動する

入力変数

変数名 名称 形式 有効範囲 初期値 内容
pointName 目標位置名 プルダウン ティーチング表で設定したポイント名（最大 100 点） P1 のポイント名 ロボットが到達する目標位置
X X 軸動作有無 プルダウン X: 有効
-: 無効 X X 軸の移動を許可
Y Y 軸動作有無 プルダウン Y: 有効
-: 無効 Y Y 軸の移動を許可
Z Z 軸動作有無 プルダウン Z: 有効
-: 無効 Z Z 軸の移動を許可
Rz Rz 軸動作有無 プルダウン Rz: 有効
-: 無効 Rz Rz 軸の移動を許可
Ry Ry 軸動作有無 プルダウン Ry: 有効
-: 無効 Ry Ry の移動を許可
Rx Rx 軸動作有無 プルダウン Rx: 有効
-: 無効 Rx Ry の移動を許可
pallet No. パレット番号 プルダウン pallet No.1 ~ 10 no pallet 目標位置をオフセットするためのパレット補正量
camera No. カメラ番号 プルダウン camera No.1 ~ 10 no camera 目標位置をオフセットするためのカメラ補正量
使用例

Dobot MG400 を目標位置"Home"へ移動する

使用上の注意

・"select"ブロックでロボットを定義してから使って下さい
・"set motor"ブロックをサーボ電源を ON にした後に使って下さい
・4 軸のロボットに対して、Rz が R(=Θ 回転)となります（Ry と Rx は無効）

moveP
ロボットを全軸絶対 PTP 移動する

入力変数

変数名 名称 形式 有効範囲 初期値 内容
pointName 目標位置名 プルダウン ティーチング表で設定したポイント名（最大 100 点） P1 のポイント名 ロボットが到達する目標位置
X X 軸動作有無 プルダウン X: 有効
-: 無効 X X 軸の移動を許可
Y Y 軸動作有無 プルダウン Y: 有効
-: 無効 Y Y 軸の移動を許可
Z Z 軸動作有無 プルダウン Z: 有効
-: 無効 Z Z 軸の移動を許可
Rz Rz 軸動作有無 プルダウン Rz: 有効
-: 無効 Rz Rz 軸の移動を許可
Ry Ry 軸動作有無 プルダウン Ry: 有効
-: 無効 Ry Ry の移動を許可
Rx Rx 軸動作有無 プルダウン Rx: 有効
-: 無効 Rx Ry の移動を許可
pallet No. パレット番号 プルダウン pallet No.1 ~ 10 no pallet 目標位置をオフセットするためのパレット補正量
camera No. カメラ番号 プルダウン camera No.1 ~ 10 no camera 目標位置をオフセットするためのカメラ補正量
使用例

Dobot MG400 を目標位置"Home"へ移動する

使用上の注意

・"select"ブロックでロボットを定義してから使って下さい
・"set motor"ブロックをサーボ電源を ON にした後に使って下さい
・4 軸のロボットに対して、Rz が R(=Θ 回転)となります（Ry と Rx は無効）

wait input
ロボット I/O の入力が指定した条件となるまで待機する

入力変数

変数名 名称 形式 有効範囲 初期値 内容
inputPinName 入力ピン名 プルダウン ロボット毎に変数名と数は異なる 番号が小さいピン名 入力を状態を取得するピン名
inputPinStatus 入力ピン操作方法 プルダウン - ON:アクティブ

- OFF:非アクティブ
  ON 対象入力ピンの状態
  使用例

"Fairino FR"の"DI00"ピンが ON するまで待機します

ロボット IO サイドバーにて、ピン名を任意の文字に変更することも可能です

使用上の注意

"select"ブロックでロボットを定義してから使って下さい

set output
ロボット I/O の出力を操作する

入力変数

変数名 名称 形式 有効範囲 初期値 内容
outputPinName 出力ピン名 プルダウン ロボット毎に異なる 番号が小さいピン名 出力を操作するピン名
outputPinStatus 出力ピン操作 プルダウン - ON:アクティブ

- OFF:非アクティブ
  ON 対象出力ピンの操作方法
  使用例

"Fairino FR"の"DO00"ピンを ON にします

ロボット IO サイドバーにて、ピン名を任意の文字に変更することも可能です

使用上の注意

"select"ブロックでロボットを定義してから使って下さい

set output during
ロボット I/O の出力を指定した時間だけ操作する

入力変数

変数名 名称 形式 有効範囲 初期値 内容
outputPinName 出力ピン名 プルダウン ロボット毎に変数名と数は異なる 番号が小さいピン名 出力を操作するピン名
outputPinStatus 出力ピン操作方法 プルダウン - ON:アクティブ

- OFF:非アクティブ
  ON 対象出力ピンの操作方法
  timerValue 出力ピン操作時間 プルダウン 変数表で設定した変数名（最大 300 点） 変数表で最初に定義した変数名 対象出力ピンの操作時間（msec）
  使用例

"Fairino FR"の"DO00"ピンを"100msec"ON にします（"_const_\*\*\*"はプルダウンメニューの下部に存在）

ロボット IO サイドバーにて、ピン名を任意の文字に変更することも可能です

使用上の注意

"select"ブロックでロボットを定義してから使って下さい

set output until
ロボット I/O の入力が指定した条件となるまで指定したピンの操作を継続する

入力変数

変数名 名称 形式 有効範囲 初期値 内容
outputPinName 出力ピン名 プルダウン ロボット毎に変数名と数は異なる 番号が小さいピン名 出力を操作するピン名
outputPinStatus 出力ピン操作方法 プルダウン - ON:アクティブ

- OFF:非アクティブ
  ON 対象出力ピンの操作方法
  inputPinName 入力ピン名 プルダウン ロボット毎に変数名と数は異なる 番号が小さいピン名 入力を状態を取得するピン名
  inputPinStatus 入力ピン操作方法 プルダウン - ON:アクティブ
- OFF:非アクティブ
  ON 対象入力ピンの状態
  使用例

"Fairino FR"の"DI00"ピンが ON になるまで"DO00"ピンを ON にします

ロボット IO サイドバーにて、ピン名を任意の文字に変更することも可能です

使用上の注意

"select"ブロックでロボットを定義してから使って下さい

robot io
ロボット I/O 状態を論理値として返す

入力変数

変数名 名称 形式 有効範囲 初期値 内容
inputPinName 入力ピン名 プルダウン ロボット毎に異なる 番号が小さいピン名 入力状態を取得するピン名
使用例

・"DO00"ピンが ON の場合、"Fairino FR"が A 点 →B 点 →D 点の順に移動します。
・"DO00"ピンが ON の場合、"Fairino FR"が A 点 →C 点 →D 点の順に移動します。

ロボット IO サイドバーにて、ピン名を任意の文字に変更することも可能です

使用上の注意

"select"ブロックでロボットを定義してから使って下さい

robot position
ロボット現在位置を数値として返す

入力変数

変数名 名称 形式 有効範囲 初期値 内容
axisName 軸名 プルダウン - X:X 軸

- Y:Y 軸
- Z:Z 軸
- Rx:Rx 軸
- Ry:Ry 軸
- Rz:Rz 軸
  番号が小さいピン名 現在位置を取得する軸名
  使用例

・現在 X 位置が 0mm 以上の場合、"Fairino FR"が A 点 →C 点の順に移動します。
・現在 X 位置が 0mm 未満の場合、"Fairino FR"が B 点 →C 点の順に移動します。

使用上の注意

"select"ブロックでロボットを定義してから使って下さい

stop robot upon
設定した条件成立でロボットが停止する

入力変数

変数名 名称 形式 有効範囲 初期値 内容
triggerCondition 動作開始条件詳細 プルダウン ・ー:常時
・↑:立ち上がり
・↓:立ち下がり
ー 動作を開始するための条件詳細
operatingCondition 動作開始条件 ブロック 論理値ブロック なし 動作を開始するための条件
使用例

"Fairino FR"が動作中に、"IO No.1"の"DI_0"が ON になるとロボットが停止します。

"Button サイドバー"にて、Pause ボタンの押下で動作の一時停止を解除できます。

その後、Run ボタンの押下で動作を再開できます。

使用上の注意

"create_event"ブロック内で使って下さい

IO
connect external io
外部機器 I/O の出力を操作する

入力変数

変数名 名称 形式 有効範囲 初期値 内容
deviceName デバイス名 プルダウン DIO000~DIO005（"ContecDeviceUtility"で設定した"Device Name"） DIO000 操作対象のデバイス名
maker メーカー プルダウン - CONTEC
CONTEC 対象 IO ユニットのメーカー
IONo IO 番号 プルダウン 1~10 IO No.1 操作対象の IO 番号
使用例

"set external io output" または "wait external io input"ブロック等を参照して下さい

使用上の注意

"set external io output" または "wait external io input"等とセットで使用して下さい

wait external io input
外部機器 I/O の入力が指定した条件となるまで待機する

入力変数

変数名 名称 形式 有効範囲 初期値 内容
IONo IO 番号 プルダウン 1~10 IO No.1 操作対象の IO 番号
inputPinName 入力ピン名 プルダウン 機器毎に異なる 番号が小さいピン名 入力を状態を取得するピン名
inputPinStatus 入力ピン操作方法 プルダウン - ON:アクティブ

- OFF:非アクティブ
  ON 対象入力ピンの状態
  使用例

"CONTEC"の"DI_0"ピンを ON するまで待機します

外部機器 IO サイドバーにて、ピン名を任意の文字に変更することも可能です

使用上の注意

"connect external io"ブロックで IO 機器を定義してから使って下さい

set external io output
外部機器 I/O の出力を操作する

入力変数

変数名 名称 形式 有効範囲 初期値 内容
IONo IO 番号 プルダウン 1~10 IO No.1 操作対象の IO 番号
outputPinName 出力ピン名 プルダウン 機器毎に異なる 番号が小さいピン名 出力を操作するピン名
outputPinStatus 出力ピン操作 プルダウン - ON:アクティブ

- OFF:非アクティブ
  ON 対象出力ピンの操作方法
  使用例

"CONTEC"の"DO_0"ピンを ON にします

外部機器 IO サイドバーにて、ピン名を任意の文字に変更することも可能です

使用上の注意

"connect external io"ブロックで IO 機器を定義してから使って下さい

set external io output during
外部機器 I/O の出力を指定した時間だけ操作する

入力変数

変数名 名称 形式 有効範囲 初期値 内容
IONo IO 番号 プルダウン 1~10 IO No.1 操作対象の IO 番号
outputPinName 出力ピン名 プルダウン 機器毎に異なる 番号が小さいピン名 出力を操作するピン名
outputPinStatus 出力ピン操作 プルダウン - ON:アクティブ

- OFF:非アクティブ
  ON 対象出力ピンの操作方法
  timerValue 待機時間 プルダウン 変数表で設定した変数名（最大 300 点） 変数表で最初に定義した変数名 動作を一時停止するための待機時間（msec）
  使用例

"CONTEC"の"DO_0"ピンを"100msec"の間 ON にします

外部機器 IO サイドバーにて、ピン名を任意の文字に変更することも可能です

使用上の注意

"connect external io"ブロックで IO 機器を定義してから使って下さい

set external io output until
外部機器 I/O の入力が指定した条件となるまで指定したピンの操作を継続する

入力変数

変数名 名称 形式 有効範囲 初期値 内容
IONo IO 番号 プルダウン 1~10 IO No.1 操作対象の IO 番号
outputPinName 出力ピン名 プルダウン 機器毎に異なる 番号が小さいピン名 出力を操作するピン名
outputPinStatus 出力ピン操作 プルダウン - ON:アクティブ

- OFF:非アクティブ
  ON 対象出力ピンの操作方法
  inputPinStatus 入力ピン操作方法 プルダウン - ON:アクティブ
- OFF:非アクティブ
  ON 対象入力ピンの状態
  使用例

"CONTEC"の"DI_0"ピンが ON になるまで"DO_0"ピンを ON にします

外部機器 IO サイドバーにて、ピン名を任意の文字に変更することも可能です

使用上の注意

"connect external io"ブロックで IO 機器を定義してから使って下さい

external io
外部機器 I/O 状態を論理値として返す

入力変数

変数名 名称 形式 有効範囲 初期値 内容
IONo IO 番号 プルダウン 1~10 IO No.1 操作対象の IO 番号
inputPinName 入力ピン名 プルダウン 機器毎に異なる 番号が小さいピン名 入力状態を取得するピン名
使用例

"stop robot upon"ブロックを参照して下さい

外部機器 IO サイドバーにて、ピン名を任意の文字に変更することも可能です

使用上の注意

"connect external io"ブロックで IO 機器を定義してから使って下さい

set external io output upon
設定した条件成立で外部機器 I/O の出力を操作する

入力変数

変数名 名称 形式 有効範囲 初期値 内容
IONo IO 番号 プルダウン 1~10 IO No.1 操作対象の IO 番号
outputPinName 出力ピン名 プルダウン 機器毎に異なる 番号が小さいピン名 出力を操作するピン名
outputPinStatus 出力ピン操作 プルダウン - ON:アクティブ

- OFF:非アクティブ
- 100msec:100msec 間隔で ON/OFF
- 300msec:300msec 間隔で ON/OFF
- 500msec:500msec 間隔で ON/OFF
- 1000msec:1000msec 間隔で ON/OFF
  ON 対象出力ピンの操作方法
  triggerCondition 動作開始条件詳細 プルダウン ・ー:常時
  ・↑:立ち上がり
  ・↓:立ち下がり
  ー 動作を開始するための条件詳細
  operatingCondition 動作開始条件 ブロック 論理値ブロック なし 動作を開始するための条件
  使用例

"Fairino FR"の運転状態に応じて、次のように出力ピンを操作します。
　- 異常停止中であれば、"DO_0"ピンを 500msec 間隔で ON/OFF
　- 定常停止中であれば、"DO_1"ピンを ON
　- 自動運転中であれば、"DO_2"ピンを ON

外部機器 IO サイドバーにて、ピン名を任意の文字に変更することも可能です

使用上の注意

・"connect external io"ブロックで IO 機器を定義してから使って下さい
・"create_event"ブロック内で使って下さい

Control
loop
内包したブロック動作のループ処理を行う

入力変数

なし

使用例

"Fairino FR"が Pick&Place ループをします

使用上の注意

・"loop"ブロックを 2 重すると意図しない動作となる場合があります
・"loop"ブロックの下に他のブロックを連結することはできません
・ループの完了は、"return"ブロックを使用して下さい

return
ループ処理の最初に戻る

入力変数

なし

使用例

"loop"ブロックを参照して下さい

使用上の注意

"loop"ブロックと一緒に使用して下さい

wait timer
指定した時間だけ待機する

入力変数

変数名 名称 形式 有効範囲 初期値 内容
timerValue 待機時間 プルダウン 変数表で設定した変数名（最大 300 点） 変数表で最初に定義した変数名 動作を一時停止するための待機時間（msec）
使用例

プログラムが開始すると 300msec 待機します（"_const_\*\*\*"はプルダウンメニューの下部に存在）

使用上の注意

・時間は msec 単位でのみ設定できます

wait ready
Ready ボタンが押下されるまで待機する

入力変数

なし

使用例

"wait run"ブロックを参照して下さい

使用上の注意

なし

wait run
Run ボタンが押下されるまで待機する

入力変数

なし

使用例

・"Button サイドバー"の"Ready"ボタンを押下すると"Fairino FR"が所定の位置まで移動します
・"Button サイドバー"の"Run"ボタンを押下すると"Fairino FR"のループ動作が開始します

使用上の注意

なし

Logic
if
条件に応じて内包した動作ブロックを分岐する

入力変数

変数名 名称 形式 有効範囲 初期値 内容
branchCondition 分岐条件 ブロック 論理値ブロック なし 動作を分岐するための条件論理値（条件分岐の追加は、歯車ボタンから可能）
使用例

"Fairino FR"が Home"位置に移動後、"Pick TOP"位置へ移動します（"Place TOP"位置には移動しません）

"Fairino FR"が Home"位置に移動後、"Place TOP"位置へ移動します（"Pick TOP"位置には移動しません）

使用上の注意

・条件分岐の最大数は 10 です
・"if"ブロックの下に他のブロックを連結することはできません
・複数の条件が同時に成立した場合は、一番最初の条件に記載した処理が優先されます

start thread
条件に応じて内包したブロック動作を開始する

入力変数

変数名 名称 形式 有効範囲 初期値 内容
startCondition 開始条件 ブロック 論理値ブロック なし 動作を開始するための条件論理値
使用例

プログラムの実行開始で、定義した変数"cnt"に 100 を代入します

使用上の注意

・"start thread"ブロックの下に他のブロックを連結することはできません

create event
設定した条件に応じて、動作の並行処理を行う

入力変数

なし

使用例

プログラムの実行開始で、定義した変数"cnt"に 100 を代入します

使用上の注意

・"start thread"ブロックの下に他のブロックを連結することはできません

wait block
接続したブロックの動作条件が成立するまで待機する

入力変数

変数名 名称 形式 有効範囲 初期値 内容
startCondition 開始条件 ブロック 論理値ブロック なし 動作を開始するための条件論理値
使用例

"logic block"ブロックを参照して下さい

使用上の注意

・動作条件として接続可能なブロックは"Logic"カテゴリのみです

set flag
変数に論理値を代入する

入力変数

変数名 名称 形式 有効範囲 初期値 内容
dstFlagVar 代入先フラグ変数 プルダウン Flag 変数表で設定した変数名（最大 300 点） Flag 変数表で最初に定義した変数 代入先の論理値型の変数
srcFlagVar 代入元フラグ変数 ブロック 数値ブロック なし 代入元の論理値型の変数
使用例

"flag1"に true を代入し、"flag2"に"flag1(=true)"を代入します

使用上の注意

変数に値を格納する前に、変数表で定義して下さい

logic flag
設定した論理値を返す

入力変数

変数名 名称 形式 有効範囲 初期値 内容
boolean 論理値 プルダウン true: 真
false: 偽
true true（真）または false（偽）の値
使用例

"start thread"ブロックを参照して下さい

使用上の注意

"start thread"ブロック等と一緒に使用して下さい

logic custom flag
定義した変数の論理値を返す

入力変数

変数名 名称 形式 有効範囲 初期値 内容
flagVar フラグ変数 プルダウン Flag 変数表で設定した変数名（最大 300 点） Flag 変数表で最初に定義した最初の変数名 論理値型の変数
使用例

"set flag"ブロックを参照して下さい

使用上の注意

"set flag"ブロック等と一緒に使用して下さい

logic block
設定したブロックの状態を論理値として返す

入力変数

変数名 名称 形式 有効範囲 初期値 内容
blockName ブロック名 プルダウン 各カテゴリに存在する上下接続可能なブロック名 moveL 状態を取得したいブロックの名前
blockNo ブロック番号 プルダウン 各カテゴリに存在する上下接続可能なブロック数 1 状態を取得したいブロックの番号
action ブロック番号 プルダウン start: 動作開始
stop: 動作完了
start 状態を取得したいブロックの動作形態
使用例

"wait timer"ブロックの動作（1000msec 待機）が完了後、"cnt"に 100 を代入します

使用上の注意

"wait block"ブロック等と一緒に使用して下さい

logic negate
設定した論理値の否定を返す

入力変数

変数名 名称 形式 有効範囲 初期値 内容
negateCondition 論理値 ブロック 論理値ブロック なし 否定したい論理値
使用例

Fairino FR"が動作中に、"IO No.1"の"DI_0"もしくは、"DI_01"が OFF になるとロボットが停止します。

使用上の注意

なし

logic compare
設定した比較演算結果を論理値として返す

入力変数

変数名 名称 形式 有効範囲 初期値 内容
leftValue 左辺値 ブロック 数値ブロック なし 演算子で比較したい数値
operator 演算子 プルダウン 6 種類
・=: イコール
・!=: ノットイコール
・<: 小なり
・<=: 小なりイコール
・>: 大なり
・>=: 大なりイコール
=(イコール) 操作を行うための演算子
rightValue 右辺値 ブロック 数値ブロック なし 演算子で比較したい数値
使用例

"cnt1"に 100 を代入した後、"cnt2"に 500 を代入します

使用上の注意

"start thread"ブロック等と一緒に使用して下さい

logic operation
設定した比較演算結果を論理値として返す

入力変数

変数名 名称 形式 有効範囲 初期値 内容
leftLogic 左辺論理 ブロック Logic カテゴリのブロック なし 演算子で比較したい論理値
operator 演算子 プルダウン 2 種類
・and: 論理積
・or: 論理和
=(イコール) 操作を行うための演算子
rightLogic 右辺論理 ブロック Logic カテゴリのブロック なし 演算子で比較したい論理値
使用例

"cnt1"に 100 を代入した後、"cnt2"に 500 を代入します

使用上の注意

"start thread"ブロック等と一緒に使用して下さい

set flag upon
設定した条件成立で変数に論理値を代入する

入力変数

変数名 名称 形式 有効範囲 初期値 内容
dstValueVar 代入先フラグ変数 プルダウン Flag 変数表で設定した変数名（最大 300 点） Flag 変数表で最初に定義した変数 代入先の論理値型の変数
srcValueVar 代入元フラグ変数 ブロック 数値ブロック なし 代入元の論理値型の変数
triggerCondition 動作開始条件詳細 プルダウン ・ー:常時
・↑:立ち上がり
・↓:立ち下がり
ー 動作を開始するための条件詳細
operatingCondition 動作開始条件 ブロック 論理値ブロック なし 動作を開始するための条件
使用例

・"DI_00"ピンが ON になると、"Fairino FR"が Pick&Place 動作を行います
・"DI_00"ピンが OFF になると、"Fairino FR"が待機します

使用上の注意

変数に値を格納する前に、変数表で定義して下さい

Math
set number
変数に値を代入する

入力変数

変数名 名称 形式 有効範囲 初期値 内容
dstValueVar 代入先数値変数 プルダウン Number 変数表で設定した変数名（最大 300 点） Number 変数表で最初に定義した変数 代入先の数値型の変数
srcValueVar 代入元数値変数 ブロック 数値ブロック なし 代入元の数値型の変数
使用例

"cnt"に 10 を代入して、500msec 待機した後、"cnt"に 11(=10+1)を代入します

使用上の注意

変数に値を格納する前に、変数表で定義して下さい

math number
数値を返す

入力変数

変数名 名称 形式 有効範囲 初期値 内容
value 数値 キーボード 32 ビット符号付き整数 0 キーボードから入力可能な任意の数値
使用例

"set number"ブロックを参照して下さい

使用上の注意

"set number"ブロック等と一緒に使用して下さい

math custom number
数値変数を指定する

入力変数

変数名 名称 形式 有効範囲 初期値 内容
valueVar 数値変数 プルダウン Number 変数表で設定した変数名（最大 300 点） Number 変数表で最初に定義した最初の変数名 数値値の変数
使用例

"set number"ブロックを参照して下さい

使用上の注意

"set number"ブロック等と一緒に使用して下さい

math arithmetic
変数に値を代入する

入力変数

変数名 名称 形式 有効範囲 初期値 内容
leftValue 左辺数値 ブロック 数値ブロック なし 演算子で比較したい数値
operator 演算子 プルダウン 5 種類
・+: 加算
・-: 減算
・\*: 乗算
・/: 除算
・^: べき乗
+(加算) 操作を行うための演算子
rightValue 右辺数値 ブロック 数値ブロック なし 演算子で比較したい数値
使用例

"set number"ブロックを参照して下さい

使用上の注意

変数に値を格納する前に、変数表で定義して下さい

set number upon
設定した条件成立で変数に値を代入する

入力変数

変数名 名称 形式 有効範囲 初期値 内容
dstValueVar 代入先数値変数 プルダウン Number 変数表で設定した変数名（最大 300 点） Number 変数表で最初に定義した変数 代入先の数値型の変数
srcValueVar 代入元数値変数 ブロック 数値ブロック なし 代入元の数値型の変数
triggerCondition 動作開始条件詳細 プルダウン ・ー:常時
・↑:立ち上がり
・↓:立ち下がり
ー 動作を開始するための条件詳細
operatingCondition 動作開始条件 ブロック 論理値ブロック なし 動作を開始するための条件
使用例

・"DI_00"ピンが ON になると、"Fairino FR"が Pick&Place 動作を行います
・"DI_00"ピンが OFF になると、"Fairino FR"が待機します

使用上の注意

変数に値を格納する前に、変数表で定義して下さい

Error
raise error
設定したエラーが即座に発生する

入力変数

変数名 名称 形式 有効範囲 初期値 内容
errorMessage エラーメッセージ 文字列 最大 50 文字 errorMessage エラー画面に表示したいアルファベットのエラーメッセージ
使用例

"Fairino FR"の Pick&Place 回数が 5 回に到達すると、設定したエラーが発生します

・"Error Reset"ボタンで発生しているエラーをリセットできます
・リセット後に再開する場合は、"Auto"ボタンを再度押下して下さい

使用上の注意

エラーメッセとして設定可能な文字列は、アルファベットのみです

raise error upon
設定した条件成立でエラーが発生する

入力変数

変数名 名称 形式 有効範囲 初期値 内容
errorMessage エラーメッセージ 文字列 最大 50 文字 errorMessage エラー画面に表示したいアルファベットのエラーメッセージ
triggerCondition 動作開始条件詳細 プルダウン ・ー:常時
・↑:立ち上がり
・↓:立ち下がり
ー 動作を開始するための条件詳細
operatingCondition 動作開始条件 ブロック 論理値ブロック なし 動作を開始するための条件
使用例

"Fairino FR"の Pick&Place 回数が 5 回に到達すると、設定したエラーが発生します

・"Error Reset"ボタンで発生しているエラーをリセットできます
・リセット後に再開する場合は、"Auto"ボタンを再度押下して下さい

使用上の注意

・エラーメッセとして設定可能な文字列は、アルファベットのみです
・"create_event"ブロック内で使って下さい

Pallet
set palet
パレット内容を設定する

入力変数

変数名 名称 形式 有効範囲 初期値 内容
rowCount 行番号 プルダウン 1~10 row=2 対象となるパレットの行番号
colCount 列番号 プルダウン 1~10 col=2 対象となるパレットの行番号
cornerPointA 点 A プルダウン ティーチング表で設定したポイント名（最大 100 点） P1 のポイント名 パレットの四隅点 A の位置名
cornerPointB 点 B プルダウン ティーチング表で設定したポイント名（最大 100 点） P1 のポイント名 パレットの四隅点 B の位置名
cornerPointC 点 C プルダウン ティーチング表で設定したポイント名（最大 100 点） P1 のポイント名 パレットの四隅点 C の位置名
cornerPointD 点 D プルダウン ティーチング表で設定したポイント名（最大 100 点） P1 のポイント名 パレットの四隅点 D の位置名
usage 使用方法 プルダウン - pick:ピック用

- place:プレース用
  pick 対象となるパレットの使用方法
  palletNo パレット番号 プルダウン 1~10 pallet No.1 対象となるパレットの番号
  使用例

・"Dobot MG400"がパレタイズ（3×3）を行い、パレットが空になるとエラーが発生します

・パレット詳細は下図のようになっています
　- 点 A と点 B の間が"rowCount"
　- 点 A と点 C の間が"colCount"
　- ロボットハンドは、点 A→B→C の方向に移動します（青矢印）

・下記サイドバーから対象のパレットの残数のモニタリングと変更できます。

使用上の注意

"move"ブロックにパレットのオフセット設定するために、pallet No.を選択して下さい

move next pallet
パレットの現在位置を次に進める

入力変数

変数名 名称 形式 有効範囲 初期値 内容
palletNo パレット番号 プルダウン 1~10 pallet No.1 対象となるパレットの番号
使用例

"set pallet"ブロックを参照して下さい

使用上の注意

"set pallet"ブロックとセットで使用して下さい

reset pallet
パレットの現在位置を始点（点 A）に戻す

入力変数

変数名 名称 形式 有効範囲 初期値 内容
palletNo パレット番号 プルダウン 1~10 pallet No.1 対象となるパレットの番号
使用例

・"Dobot MG400"がパレタイズ（3×3）を永続的に行います

使用上の注意

"set pallet"ブロックとセットで使用して下さい

Camera
connect camera
カメラ PC と接続する

入力変数

変数名 名称 形式 有効範囲 初期値 内容
octetNo1 第 1 オクテット キーボード 8 ビット符号無し整数 127 対象カメラ PC の IP アドレス第 1 オクテット
octetNo2 第 2 オクテット キーボード 8 ビット符号無し整数 0 対象カメラ PC の IP アドレス第 2 オクテット
octetNo3 第 3 オクテット キーボード 8 ビット符号無し整数 0 対象カメラ PC の IP アドレス第 3 オクテット
octetNo4 第 4 オクテット キーボード 8 ビット符号無し整数 1 対象カメラ PC の IP アドレス第 4 オクテット
protNo ポート番号 プルダウン 1024~65535 5000 対象カメラ PC のポート番号
使用例

"run camera wait" または "run camera"ブロックを参照して下さい

使用上の注意

"run camera wait" または "run camera"ブロック等とセットで使用して下さい

run camera wait
カメラ PC に実行命令を送信し、結果を取得するまで待機する

入力変数

変数名 名称 形式 有効範囲 初期値 内容
cameraNo カメラ番号 プルダウン 1~10 camera No.1 カメラの接続を区別するために付与した任意の番号
programNo プログラム番号 プルダウン 1~100 program No.1 カメラ PC で実行中のプログラム番号。この番号をカメラ PC に送信する
使用例

カメラ No.1 からの結果が 1(=OK)ならば、"Hitbot Z ARM"がカメラ No.1 から取得した補正値を使って Pick&Place します

使用上の注意

・"connect camera"ブロック等とセットで使用して下さい
・Facilea、Vision Master、VAST Vision などのビジョンと連携が可能です
　詳細については、使用するビジョンの資料をご確認下さい
・カメラ動作命令について、TCP 経由で文字列形式の電文を送信しており、内容は下記です
　※プログラム番号のみ、ブロックから値を変更できます
「識別ヘッダー,プログラム番号,コンフィグ番号,モデル番号,ポジション番号 CRLF」
　　例. TR1,1,0,0,0\r\n
・カメラ結果受信について、TCP 経由で文字列形式の電文を受信しており、内容は下記です
「識別ヘッダー,判定結果(OK:1, NG:2, ERR:3),x 座標[mm],y 座標,z 座標,Θ,判定内容（テキスト）CRLF」
　　例. TR1,1,0,0,0,0,no work,\r\n

run camera
カメラ PC に実行命令を送信する

入力変数

変数名 名称 形式 有効範囲 初期値 内容
cameraNo カメラ番号 プルダウン 1~10 camera No.1 カメラの接続を区別するために付与した任意の番号
programNo プログラム番号 プルダウン 1~100 program No.1 カメラ PC で実行中のプログラム番号。この番号をカメラ PC に送信する
使用例

・カメラ No.1 からの結果が 1(=OK)ならば、"Hitbot Z ARM"がカメラ No.1 から取得した補正値を使って Pick&Place します
・ロボットの Home 位置への移動とカメラの検出を、並列で行います

使用上の注意

・"connect camera"ブロック等とセットで使用して下さい
・Facilea、Vision Master、VAST Vision などのビジョンと連携が可能です
　詳細については、使用するビジョンの資料をご確認下さい
・カメラ動作命令について、TCP 経由で文字列形式の電文を送信しており、内容は下記です
　※プログラム番号のみ、ブロックから値を変更できます
「識別ヘッダー,プログラム番号,コンフィグ番号,モデル番号,ポジション番号 CRLF」
　　例. TR1,1,0,0,0\r\n

wait camera
カメラ PC から結果を取得するまで待機する

入力変数

変数名 名称 形式 有効範囲 初期値 内容
cameraNo カメラ番号 プルダウン 1~10 camera No.1 カメラの接続を区別するために付与した任意の番号
使用例

"run camera"ブロックを参照して下さい

使用上の注意

"run camera"ブロック等とセットで使用して下さい

PLC
connect plc
PLC と接続する

入力変数

変数名 名称 形式 有効範囲 初期値 内容
maker メーカー プルダウン - KEYENCE
KEYENCE 対象 PLC のメーカー
octetNo1 第 1 オクテット キーボード 8 ビット符号無し整数 192 対象 PLC の IP アドレス第 1 オクテット
octetNo2 第 2 オクテット キーボード 8 ビット符号無し整数 168 対象 PLC の IP アドレス第 2 オクテット
octetNo3 第 3 オクテット キーボード 8 ビット符号無し整数 250 対象 PLC の IP アドレス第 3 オクテット
octetNo4 第 4 オクテット キーボード 8 ビット符号無し整数 10 対象 PLC の IP アドレス第 4 オクテット
protNo ポート番号 プルダウン 1024~65535 5000 対象 PLC のポート番号
使用例

"plc bit" または "set plc bit"ブロック等を参照して下さい

使用上の注意

"plc bit" または "set plc bit"ブロック等とセットで使用して下さい

plc bit
PLC の bit デバイスの取得結果を論理値として返す

入力変数

変数名 名称 形式 有効範囲 初期値 内容
deviceName デバイス名 プルダウン - R デバイス

- MR デバイス
  R PLC から取得する対象デバイス名の名前
  deviceWordNo デバイス WORD 番号 キーボード 対象メーカーの機種ごとに異なる 0 PLC から取得する対象デバイス名の WORD 番号
  deviceBitNo デバイス BIT 番号 プルダウン 00~16 00 PLC から取得する対象デバイス名の BIT 番号
  使用例

"KEYENCE"製 PLC の"R000"デバイスが ON の時に、"R001"デバイスを ON にします

使用上の注意

"connect plc"ブロックとセットで使用して下さい

plc word
PLC の word デバイスの取得結果を数値として返す

入力変数

変数名 名称 形式 有効範囲 初期値 内容
deviceName デバイス名 プルダウン - DM デバイス
DM PLC から取得する対象デバイス名の名前
deviceWordNo デバイス WORD 番号 キーボード 対象メーカーの機種ごとに異なる 0 PLC から取得する対象デバイス名の WORD 番号
使用例

"KEYENCE"製 PLC の"DM1000"デバイスが"100"の時に、"DM1001"デバイスを"200"にします

使用上の注意

"connect plc"ブロックとセットで使用して下さい

set plc bit
PLC の bit デバイスの値を操作する

入力変数

変数名 名称 形式 有効範囲 初期値 内容
deviceName デバイス名 プルダウン - R デバイス

- MR デバイス
  R PLC から取得する対象デバイス名の名前
  deviceWordNo デバイス WORD 番号 キーボード 対象メーカーの機種ごとに異なる 0 PLC から取得する対象デバイス名の WORD 番号
  deviceBitNo デバイス BIT 番号 プルダウン 00~16 00 PLC から取得する対象デバイス名の BIT 番号
  bitStatus ビット状態 プルダウン - ON:アクティブ
- OFF:非アクティブ
  ON 対象ビットデバイスの操作方法
  使用例

"KEYENCE"製 PLC の"MR1000"デバイスを"ON"にします

使用上の注意

"connect plc"ブロックとセットで使用して下さい

set plc bit during
PLC の bit デバイスの値を指定した時間だけ操作する

入力変数

変数名 名称 形式 有効範囲 初期値 内容
deviceName デバイス名 プルダウン - R デバイス

- MR デバイス
  R PLC から取得する対象デバイス名の名前
  deviceWordNo デバイス WORD 番号 キーボード 対象メーカーの機種ごとに異なる 0 PLC から取得する対象デバイス名の WORD 番号
  deviceBitNo デバイス BIT 番号 プルダウン 00~16 00 PLC から取得する対象デバイス名の BIT 番号
  bitStatus ビット状態 プルダウン - ON:アクティブ
- OFF:非アクティブ
  ON 対象ビットデバイスの操作方法
  timerValue ビット操作時間 プルダウン 変数表で設定した変数名（最大 300 点） 変数表で最初に定義した変数名 ビットの操作時間（msec）
  使用例

"KEYENCE"製 PLC の"MR1000"デバイスを"3 秒間"だけ"ON"にします

使用上の注意

"connect plc"ブロックとセットで使用して下さい

set plc bit until
PLC の bit デバイスの値を指定した条件が成立するまで操作する

入力変数

変数名 名称 形式 有効範囲 初期値 内容
outDeviceName 出力デバイス名 プルダウン - R デバイス

- MR デバイス
  R PLC から取得する対象デバイス名の名前
  outDeviceWordNo 出力デバイス WORD 番号 キーボード 対象メーカーの機種ごとに異なる 0 PLC から取得する対象デバイス名の WORD 番号
  outDeviceBitNo 出力デバイス BIT 番号 プルダウン 00~16 00 PLC から取得する対象デバイス名の BIT 番号
  outBitStatus 出力ビット状態 プルダウン - ON:アクティブ
- OFF:非アクティブ
  ON 対象ビットデバイスの操作方法
  inDeviceName 入力デバイス名 プルダウン - R デバイス
- MR デバイス
  R PLC から取得する対象デバイス名の名前
  inDeviceWordNo 入力デバイス WORD 番号 キーボード 対象メーカーの機種ごとに異なる 0 PLC から取得する対象デバイス名の WORD 番号
  inDeviceBitNo 入力デバイス BIT 番号 プルダウン 00~16 00 PLC から取得する対象デバイス名の BIT 番号
  inBitStatus 入力ビット状態 プルダウン - ON:アクティブ
- OFF:非アクティブ
  ON 対象ビットデバイスの操作方法
  使用例

"KEYENCE"製 PLC の"R1000"デバイスが"ON"になるまでの間"MR1000"デバイスを"ON"にします

使用上の注意

"connect plc"ブロックとセットで使用して下さい

set plc word
PLC の bit デバイスの値を操作する

入力変数

変数名 名称 形式 有効範囲 初期値 内容
value 数値 キーボード 0~65536 0 対象デバイスへ格納する数値
deviceName デバイス名 プルダウン - DM デバイス
DM PLC から取得する対象デバイス名の名前
deviceWordNo デバイス WORD 番号 キーボード 対象メーカーの機種ごとに異なる 0 PLC から取得する対象デバイス名の WORD 番号
使用例

"KEYENCE"製 PLC の"DM1000"デバイスを"123"にします

使用上の注意

"connect plc"ブロックとセットで使用して下さい

Function
define function
関数を定義する

入力変数

変数名 名称 形式 有効範囲 初期値 内容
functionName 関数名 キーボード 最大 50 文字 do something 関数の名前
使用例

"call function"ブロックを参照して下さい

使用上の注意

・"call function"ブロックとセットで使用して下さい
・"define function"ブロックを消去すると、同一名の"call function"ブロックも削除されます

call function
定義した関数を呼び出す

入力変数

なし

使用例

"Fairino FR"が Pick&Place ループをします

使用上の注意

使用する前に"call function"ブロックで定義して下さい
