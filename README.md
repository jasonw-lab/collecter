<!-- ...existing code... -->

## 使い方

### ディレクトリ内の全画像を処理

```bash
python3 collect.py --images-dir images --csv output.csv
```

### 単一の画像ファイルを処理

```bash
python3 collect.py --image-file 1015.jpg --csv output.csv --overwrite
```

### オプション

- `--csv`: 出力CSVファイル名 (デフォルト: output.csv)
- `--images-dir`: 画像ディレクトリ (デフォルト: images)
- `--image-file`: 処理する単一の画像ファイル
- `--sleep`: API呼び出し間のスリープ時間(秒) (デフォルト: 1.0)
- `--overwrite`: 既存のCSVファイルを上書き

<!-- ...existing code... -->

