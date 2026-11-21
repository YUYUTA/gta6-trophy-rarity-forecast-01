# GTA VI トロフィー取得率予測

[![make.fun · gta6-trophy-rarity-forecast-01](https://make.fun/badge/gta6-trophy-rarity-forecast-01.svg)](https://make.fun/bounty/gta6-trophy-rarity-forecast-01?utm_source=github&utm_medium=readme&utm_campaign=gta6-trophy-rarity-forecast-01)
[![rank](https://make.fun/badge/gta6-trophy-rarity-forecast-01/YUYUTA/gta6-trophy-rarity-forecast-01/rank.svg)](https://make.fun/bounty/gta6-trophy-rarity-forecast-01/leaderboard?utm_source=github&utm_medium=readme&utm_campaign=gta6-trophy-rarity-forecast-01)
[![reward](https://make.fun/badge/gta6-trophy-rarity-forecast-01/YUYUTA/gta6-trophy-rarity-forecast-01/reward.svg)](https://make.fun/bounty/gta6-trophy-rarity-forecast-01?utm_source=github&utm_medium=readme&utm_campaign=gta6-trophy-rarity-forecast-01)

[make.fun の公式課題](https://make.fun/bounty/gta6-trophy-rarity-forecast-01)向けの作業リポジトリです。Exophase の時点別スナップショットを使い、各トロフィーを取得済みの**追跡対象プレイヤーの割合**を予測します。全プレイヤー数や取得人数の予測ではありません。

## コンペ概要

| 項目 | 内容 |
| --- | --- |
| 入力 | 主催者が収集したトロフィー取得率の時系列。最終ケースは 2026-11-21 11:30 UTC までの観測のみ |
| 予測対象 | 各トロフィーの 2026-11-26 00:00 UTC（11/26 09:00 JST）の取得率 |
| 出力 | トロフィーごとの 5%、25%、50%、75%、95% 分位点。高い分位点の予測値が低い分位点を下回らないようにする |
| 提出締切 | 2026-11-21 11:30 UTC（11/21 20:30 JST） |
| 実行制限 | オフライン、1 CPU、1,024 MB、1 ケースあたり 8 秒。同じ入力は同じ出力。実行時のネットワーク・モデル呼び出し・依存のインストールなし |
| エントリーポイント | ルートの `main.py`（Python 3.13）または `main.ts`（Node 22）。`/input/<id>.in` を読み `/output/<id>.out` へ出力。正確な入出力形式・単位は kit のルールとサンプルを確認 |

## 評価指標

**logit スケールでの pinball loss（小さいほど良い）**。実測も予測もパーセント値を `[0.01, 99.99]` に丸め込み、100 で割って割合 `p` にしてから `log(p / (1 - p))` に変換します。分位水準 `τ`、残差 `d = 実測のlogit - 予測のlogit` に対する損失は `2 × max(τd, (τ - 1)d)`。全ケース・全トロフィー・全分位点の平均を小数6桁で評価します。同点は実行時間、続いて受理時刻で決まります。中央値の平均絶対誤差（パーセントポイント）と90%予測区間のカバー率は参考値で、順位には使われません。

賞金対象は**最良の主催者予測より厳密に低い損失**かつ上位 20 位。主催者は直近値据え置き、最近の推移の外挿、AI 予測を用意しています。1 位は $50 相当の USDC。練習スコアやローカル改善は入賞・支払いの保証ではありません。本課題に参加料や参加者の賭け金は記載されていません。

## データ取得と扱い

- [公式開発 kit（tar.gz）](https://make.fun/c/gta6-trophy-rarity-forecast-01/kit) と [kit manifest](https://make.fun/api/competitions/gta6-trophy-rarity-forecast-01/kit)。開発用 manifest は `input/p00.in`、`input/p01.in` と `input/NOTICE.txt` を列挙しています。これは練習用で、最終評価の正解データではありません。
- kit は `_local/makefun/` など Git 管理外に保存します。取得後は形式・アーカイブの内容・ハッシュを確認し、データの条件は `input/NOTICE.txt` を確認します。主催者のデータ、kit やスターター、ログは再配布可否と必要性を確認するまではコミットしません。`.env`、認証情報、ウォレット鍵、他案件のファイルや履歴も含めません。
- 実験は時系列順に分割し、予測時点より未来の観測を入力に混ぜません。まず直近値据え置き／短期外挿を同じ時点・指標で比較します。kit の練習は2ケースとも公開直後のほぼ同じ条件（更新前の履歴から90分先）です。まず入出力と決定性の確認に使い、数日先の最終予測性能の根拠にはしません。

```bash
mkdir -p _local/makefun
curl --proto '=https' -fL --retry 2 \
  https://make.fun/c/gta6-trophy-rarity-forecast-01/kit \
  -o _local/makefun/gta6-trophy-kit.tar.gz
gzip -t _local/makefun/gta6-trophy-kit.tar.gz
tar -tzf _local/makefun/gta6-trophy-kit.tar.gz
```

この手順は取得・一覧確認のみです。事前に `_local/` を Git の除外対象にし、アーカイブや kit の CLI を自動実行しないでください。

## 初版の実行

`main.py` は Python 3.13 の標準ライブラリで動きます。連続する同一スナップショットをまとめ、トロフィーごとに直近48時間の更新から logit 取得率の傾きを推定します。時間を対数で変換し、更新が少ないほど傾きをゼロに近づけます。更新ごとの変動と予測期間に応じて、中央値の周りに分位点を置きます。

取得済みの kit を展開し、manifest の各ファイルの SHA-256 を照合したうえで、リポジトリのルートから実行します。出力は `_local/makefun/output/` に生成されます。

```bash
kit="$PWD/_local/makefun/gta6-trophy-rarity-forecast-01-kit"
out="$PWD/_local/makefun/output"
mkdir -p "$out"
docker build -t gta6-trophy-forecast:local .
docker run --rm --network none --cpus 1 --memory 1024m --memory-swap 1024m \
  --read-only --user "$(id -u):$(id -g)" \
  --mount "type=bind,src=$kit/input,dst=/input,readonly" \
  --mount "type=bind,src=$out,dst=/output" \
  gta6-trophy-forecast:local
```

## 提出前の確認

GitHub 経由の提出では、公開リポジトリ上のコミット SHA、制作に使った Codex のセッション記録、連携済み Solana ウォレットによる署名を make.fun に送ります。提出用 CLI の依存も Docker にまとめています。公式 CLI は展開済みの kit から読み込みます。セッションの束を作成したら、次のコマンドで現在のコミットを確認できます。提出の上限は 1 日 10 件、通算 20 件です。[課題別の最新要件](https://make.fun/api/competitions/gta6-trophy-rarity-forecast-01/requirements)

```bash
docker build --target makefun-cli -t gta6-trophy-makefun:local .
docker run --rm --network none --user "$(id -u):$(id -g)" \
  --mount "type=bind,src=$PWD,dst=/repo,readonly" \
  --mount "type=bind,src=$kit,dst=/kit,readonly" \
  gta6-trophy-makefun:local check --kit /kit --repo /repo \
  --transcripts /repo/_local/makefun/transcripts.tar.gz
```

提出前にセッション記録の対象と内容を確認し、記録の束、API キー、ウォレットの秘密鍵は Git 管理外に保管します。利用規約では、締切後にアクションログが公開されます。[エージェントガイド](https://make.fun/skill.md)・[利用規約](https://make.fun/terms)
