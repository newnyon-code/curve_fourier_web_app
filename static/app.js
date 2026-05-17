const canvas = document.getElementById("drawCanvas");
const ctx = canvas.getContext("2d");
const pointStatus = document.getElementById("pointStatus");
const analyzeBtn = document.getElementById("analyzeBtn");
const clearBtn = document.getElementById("clearBtn");
const circleBtn = document.getElementById("circleBtn");
const coastBtn = document.getElementById("coastBtn");
const message = document.getElementById("message");
const runId = document.getElementById("runId");
const summaryGrid = document.getElementById("summaryGrid");
const reconstructionImg = document.getElementById("reconstructionImg");
const errorImg = document.getElementById("errorImg");
const downloads = document.getElementById("downloads");

let points = [];
let drawing = false;

function canvasPoint(event) {
    const rect = canvas.getBoundingClientRect();
    return {
        x: (event.clientX - rect.left) * canvas.width / rect.width,
        y: (event.clientY - rect.top) * canvas.height / rect.height
    };
}

function updateStatus() {
    pointStatus.textContent = `${points.length} points`;
}

function resetCanvas() {
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    ctx.fillStyle = "#ffffff";
    ctx.fillRect(0, 0, canvas.width, canvas.height);
}

function drawAll(closePath) {
    resetCanvas();
    if (points.length === 0) {
        return;
    }
    ctx.lineWidth = 3;
    ctx.lineCap = "round";
    ctx.lineJoin = "round";
    ctx.strokeStyle = "#17335f";
    ctx.beginPath();
    ctx.moveTo(points[0].x, points[0].y);
    for (let i = 1; i < points.length; i += 1) {
        ctx.lineTo(points[i].x, points[i].y);
    }
    if (closePath && points.length > 2) {
        ctx.lineTo(points[0].x, points[0].y);
    }
    ctx.stroke();
    ctx.fillStyle = "#2f5fff";
    ctx.beginPath();
    ctx.arc(points[0].x, points[0].y, 4, 0, Math.PI * 2);
    ctx.fill();
}

function addPoint(point) {
    const last = points[points.length - 1];
    if (last) {
        const dx = point.x - last.x;
        const dy = point.y - last.y;
        if (Math.hypot(dx, dy) < 2) {
            return;
        }
    }
    points.push(point);
    updateStatus();
}

canvas.addEventListener("pointerdown", event => {
    drawing = true;
    canvas.setPointerCapture(event.pointerId);
    const point = canvasPoint(event);
    if (points.length === 0) {
        resetCanvas();
    }
    addPoint(point);
    drawAll(false);
});

canvas.addEventListener("pointermove", event => {
    if (!drawing) {
        return;
    }
    addPoint(canvasPoint(event));
    drawAll(false);
});

canvas.addEventListener("pointerup", event => {
    drawing = false;
    canvas.releasePointerCapture(event.pointerId);
    drawAll(true);
});

canvas.addEventListener("pointerleave", () => {
    drawing = false;
    drawAll(true);
});

function clearResult() {
    reconstructionImg.style.display = "none";
    errorImg.style.display = "none";
    reconstructionImg.removeAttribute("src");
    errorImg.removeAttribute("src");
    downloads.innerHTML = "";
    runId.textContent = "ready";
    summaryGrid.innerHTML = `
        <div><span>안정적 N*</span><strong>-</strong></div>
        <div><span>오차 최소 N</span><strong>-</strong></div>
        <div><span>추정 둘레</span><strong>-</strong></div>
        <div><span>기준 둘레</span><strong>-</strong></div>
    `;
}

clearBtn.addEventListener("click", () => {
    points = [];
    resetCanvas();
    updateStatus();
    clearResult();
    message.textContent = "초기화되었습니다. 새 폐곡선을 그려보세요.";
});

function setGeneratedCurve(generator, count) {
    points = [];
    for (let i = 0; i < count; i += 1) {
        const t = i / count;
        points.push(generator(t));
    }
    drawAll(true);
    updateStatus();
}

circleBtn.addEventListener("click", () => {
    const cx = canvas.width / 2;
    const cy = canvas.height / 2;
    const r = Math.min(canvas.width, canvas.height) * 0.32;
    setGeneratedCurve(t => {
        const a = Math.PI * 2 * t;
        return {x: cx + r * Math.cos(a), y: cy + r * Math.sin(a)};
    }, 420);
    message.textContent = "원 예시를 불러왔습니다. 이론적으로는 N=1에서 충분히 복원됩니다.";
});

coastBtn.addEventListener("click", () => {
    const cx = canvas.width / 2;
    const cy = canvas.height / 2;
    const base = Math.min(canvas.width, canvas.height) * 0.28;
    setGeneratedCurve(t => {
        const a = Math.PI * 2 * t;
        const r = base * (1 + 0.22 * Math.sin(5 * a + 0.4) + 0.10 * Math.sin(11 * a) + 0.035 * Math.sin(83 * a));
        return {x: cx + r * Math.cos(a), y: cy + r * Math.sin(a)};
    }, 900);
    message.textContent = "해안선형 예시를 불러왔습니다. 낮은 N은 형태를 단순화하고 높은 N은 미세 요철까지 따라갑니다.";
});

function readNumber(id) {
    return Number(document.getElementById(id).value);
}

function formatNumber(value) {
    if (!Number.isFinite(value)) {
        return "-";
    }
    if (Math.abs(value) >= 1000) {
        return value.toFixed(1);
    }
    return value.toFixed(4);
}

function renderSummary(summary) {
    summaryGrid.innerHTML = `
        <div><span>안정적 N*</span><strong>${summary.recommended_N}</strong></div>
        <div><span>오차 최소 N</span><strong>${summary.min_error_N}</strong></div>
        <div><span>추정 둘레</span><strong>${formatNumber(summary.recommended_fourier_perimeter)}</strong></div>
        <div><span>기준 둘레</span><strong>${formatNumber(summary.reference_polygon_perimeter)}</strong></div>
    `;
}

function renderDownloads(items) {
    downloads.innerHTML = "";
    const labels = {
        curve_csv: "폐곡선 CSV",
        order_analysis_csv: "N별 분석 CSV",
        fourier_coefficients_csv: "계수 CSV",
        summary_json: "요약 JSON"
    };
    for (const [key, url] of Object.entries(items)) {
        const a = document.createElement("a");
        a.href = url;
        a.textContent = labels[key] || key;
        a.target = "_blank";
        downloads.appendChild(a);
    }
}

analyzeBtn.addEventListener("click", async () => {
    if (points.length < 20) {
        message.textContent = "점을 20개 이상 그린 뒤 분석하세요.";
        return;
    }
    analyzeBtn.disabled = true;
    analyzeBtn.textContent = "분석 중";
    drawAll(true);
    message.textContent = "푸리에 계수와 N별 둘레를 계산하는 중입니다.";
    try {
        const response = await fetch("/api/analyze", {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify({
                points,
                samples: readNumber("samples"),
                max_order: readNumber("maxOrder"),
                perimeter_samples: readNumber("perimeterSamples"),
                slope_tol: readNumber("slopeTol"),
                rmse_tol: readNumber("rmseTol"),
                energy_tol: readNumber("energyTol"),
                window: readNumber("window")
            })
        });
        const result = await response.json();
        if (!result.ok) {
            throw new Error(result.message || "분석에 실패했습니다.");
        }
        const cache = `?v=${Date.now()}`;
        reconstructionImg.src = result.images.curve_reconstruction + cache;
        errorImg.src = result.images.error_vs_N + cache;
        reconstructionImg.style.display = "block";
        errorImg.style.display = "block";
        renderSummary(result.summary);
        renderDownloads(result.downloads);
        runId.textContent = result.run_id;
        message.textContent = `분석 완료: 안정적 N*=${result.summary.recommended_N}, 오차 최소 N=${result.summary.min_error_N}`;
    } catch (error) {
        message.textContent = error.message;
    } finally {
        analyzeBtn.disabled = false;
        analyzeBtn.textContent = "분석 실행";
    }
});

resetCanvas();
updateStatus();
