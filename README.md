# 복소 푸리에 폐곡선 웹 앱

## 실행

Windows PowerShell 또는 Visual Studio 터미널에서:

```bash
py -m pip install -r requirements.txt
py app.py
```

Mac/Linux에서:

```bash
python3 -m pip install -r requirements.txt
python3 app.py
```

실행 뒤 브라우저에서 다음 주소를 엽니다.

```text
http://127.0.0.1:5000
```

## 기능

캔버스에 폐곡선을 직접 그린 뒤 분석 실행을 누르면 다음 파일이 생성됩니다.

```text
static/runs/<run_id>/curve_reconstruction.jpg
static/runs/<run_id>/error_vs._N.jpg
static/runs/<run_id>/drawn_curve_resampled.csv
static/runs/<run_id>/order_analysis.csv
static/runs/<run_id>/fourier_coefficients.csv
static/runs/<run_id>/summary.json
```

웹 화면에는 `curve_reconstruction.jpg`와 `error_vs._N.jpg`가 바로 표시됩니다.

## 기본 파라미터

```text
samples = 1024
max_order = 80
perimeter_samples = 4096
epsilon = 0.006
rmse_tol = 0.040
energy_eta = 0.985
q = 3
```

안정적 N은 둘레 변화율, 정규화 RMSE, 계수 에너지 조건을 함께 사용합니다. 원처럼 단순한 곡선은 안정 구간의 시작점을 반환하도록 수정되어 있습니다.
