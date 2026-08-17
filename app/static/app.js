// JavaScript for Japan GIS Pipeline Dashboard (DEM & Slope Map Edition)

document.addEventListener('DOMContentLoaded', () => {
    let prefectures = [];
    let currentPref = null;
    let currentCity = 'ALL';
    let selectedResolution = '5m';
    let map = null;
    let boundaryLayer = null;
    let liveZukakuLayerGroup = null;
    let animatedFeatureIds = new Set();
    let eventSource = null;
    let pollTimer = null;
    let animTimer = null;

    // UI Elements
    const prefSelect = document.getElementById('pref-select');
    const citySelect = document.getElementById('city-select');
    const infoName = document.getElementById('info-pref-name');
    const infoSystem = document.getElementById('info-system');
    const infoEpsg = document.getElementById('info-epsg');
    const infoTargetArea = document.getElementById('info-target-area');

    const btnRes5m = document.getElementById('btn-res-5m');
    const btnRes10m = document.getElementById('btn-res-10m');
    const demAvailStatus = document.getElementById('dem-avail-status');
    const chkGenerateSlope = document.getElementById('chk-generate-slope');

    const btnStart = document.getElementById('btn-start');
    const btnCancel = document.getElementById('btn-cancel');
    const statusBadge = document.getElementById('status-badge');
    const progressFill = document.getElementById('progress-fill');
    const progressText = document.getElementById('progress-text');
    const progressPct = document.getElementById('progress-pct');
    const logWindow = document.getElementById('log-window');

    const btnDownloadZip = document.getElementById('btn-download-zip');
    const statZukaku = document.getElementById('stat-zukaku');
    const statResolution = document.getElementById('stat-resolution');
    const statElevationRange = document.getElementById('stat-elevation-range');
    const statMeanElevation = document.getElementById('stat-mean-elevation');
    const mapTargetLabel = document.getElementById('map-target-label');

    // 1. マップ初期化
    initMap();

    // 2. 解像度ボタンイベント
    btnRes5m.addEventListener('click', () => {
        if (btnRes5m.disabled) return;
        selectedResolution = '5m';
        btnRes5m.classList.add('active');
        btnRes10m.classList.remove('active');
    });

    btnRes10m.addEventListener('click', () => {
        if (btnRes10m.disabled) return;
        selectedResolution = '10m';
        btnRes10m.classList.add('active');
        btnRes5m.classList.remove('active');
    });

    // 3. 都道府県一覧の取得
    fetch('/api/prefectures')
        .then(res => res.json())
        .then(data => {
            prefectures = data;
            populatePrefectures(data);
        })
        .catch(err => {
            console.error('Prefectures fetch error:', err);
            logMessage(`初期化エラー: 都道府県データを取得できませんでした (${err})`, 'error');
        });

    function populatePrefectures(data) {
        prefSelect.innerHTML = '<option value="">-- 都道府県を選択してください --</option>';
        data.forEach(p => {
            const opt = document.createElement('option');
            opt.value = p.code;
            opt.textContent = `${p.code}. ${p.name} (第${p.system}系)`;
            prefSelect.appendChild(opt);
        });
        prefSelect.value = "";
        citySelect.disabled = true;
        citySelect.innerHTML = '<option value="">-- 都道府県を選択してください --</option>';
        btnStart.disabled = true;
    }

    prefSelect.addEventListener('change', (e) => {
        const val = e.target.value;
        if (!val) {
            resetToUnselectedState();
            return;
        }
        btnStart.disabled = false;
        selectPrefecture(val);
    });

    citySelect.addEventListener('change', (e) => {
        currentCity = e.target.value || 'ALL';
        infoTargetArea.textContent = (currentCity === 'ALL' || !currentCity) ? '都道府県全域' : currentCity;
        if (currentPref) {
            zoomToBoundary(currentPref.code, currentCity);
        }
    });

    function resetToUnselectedState() {
        currentPref = null;
        currentCity = 'ALL';
        infoName.textContent = '未選択';
        infoSystem.textContent = '第-系';
        infoEpsg.textContent = 'EPSG:-';
        infoTargetArea.textContent = '全国マップ表示中';
        citySelect.disabled = true;
        citySelect.innerHTML = '<option value="">-- 都道府県を選択してください --</option>';
        btnStart.disabled = true;
        demAvailStatus.textContent = '自治体を選択すると整備状況を確認します';
        btnRes5m.disabled = false;
        btnRes10m.disabled = false;
        
        clearAllMapLayers(false);
        map.setView([36.5, 137.5], 5.5, { animate: true });
        mapTargetLabel.textContent = '日本列島全域マップ (自治体を選択すると位置へズームインします)';
    }

    function selectPrefecture(code) {
        currentPref = prefectures.find(p => p.code === code);
        if (currentPref) {
            infoName.textContent = currentPref.name;
            infoSystem.textContent = `第${currentPref.system}系`;
            infoEpsg.textContent = `EPSG:${currentPref.epsg}`;

            fetchMunicipalities(currentPref.code);
        }
    }

    function fetchMunicipalities(prefCode) {
        citySelect.disabled = true;
        citySelect.innerHTML = '<option value="ALL">⏳ 市町村リストを読み込み中... お待たせしております</option>';
        currentCity = 'ALL';
        infoTargetArea.textContent = '都道府県全域';

        fetch(`/api/municipalities/${prefCode}`)
            .then(res => res.json())
            .then(data => {
                citySelect.innerHTML = '<option value="ALL">【全域】都道府県全域</option>';
                const cities = data.municipalities || [];
                cities.forEach(c => {
                    const opt = document.createElement('option');
                    opt.value = c;
                    opt.textContent = c;
                    citySelect.appendChild(opt);
                });
                citySelect.disabled = false;
                zoomToBoundary(prefCode, 'ALL');
            })
            .catch(err => {
                console.log('Municipalities fetch error:', err);
                citySelect.innerHTML = '<option value="ALL">【全域】都道府県全域</option>';
                citySelect.disabled = false;
                zoomToBoundary(prefCode, 'ALL');
            });
    }

    function zoomToBoundary(prefCode, city) {
        initMap();
        const areaTitle = (city && city !== 'ALL') ? `${currentPref.name} ${city}` : `${currentPref.name} 全域`;
        
        if (boundaryLayer) {
            map.removeLayer(boundaryLayer);
            boundaryLayer = null;
        }

        mapTargetLabel.innerHTML = `⏳ ${areaTitle} の位置データを取得・DEM整備状況確認中...`;
        progressText.textContent = `⏳ ${areaTitle} の境界データおよびDEM整備情報を確認中...`;
        prefSelect.disabled = true;
        citySelect.disabled = true;
        btnStart.disabled = true;
        demAvailStatus.textContent = '⏳ DEM整備状況を判定中...';

        let url = `/api/boundary-polygon/${prefCode}`;
        if (city && city !== 'ALL') {
            url += `?city_name=${encodeURIComponent(city)}`;
        }

        let checkUrl = `/api/check-dem-availability/${prefCode}`;
        if (city && city !== 'ALL') {
            checkUrl += `?city_name=${encodeURIComponent(city)}`;
        }

        fetch(checkUrl)
            .then(res => res.json())
            .then(avail => {
                btnRes5m.disabled = !avail['5m'];
                btnRes10m.disabled = !avail['10m'];

                if (!avail['5m'] && selectedResolution === '5m') {
                    selectedResolution = '10m';
                    btnRes10m.classList.add('active');
                    btnRes5m.classList.remove('active');
                }

                if (avail['5m'] && avail['10m']) {
                    demAvailStatus.textContent = '🟢 5m / 10m メッシュ共に整備されています';
                } else if (avail['10m']) {
                    demAvailStatus.textContent = '🟠 10m メッシュのみ利用可能です (5m未整備)';
                } else {
                    demAvailStatus.textContent = '⚪ 国土地理院 DEM のサンプル取得を確認できませんでした';
                }
            })
            .catch(err => {
                demAvailStatus.textContent = 'ℹ️ 10m メッシュ推奨';
            });

        fetch(url)
            .then(res => {
                if (!res.ok) throw new Error('Boundary not found');
                return res.json();
            })
            .then(geojson => {
                boundaryLayer = L.geoJSON(geojson, {
                    style: {
                        color: '#06b6d4',
                        weight: 2.5,
                        dashArray: '5, 5',
                        fillColor: '#06b6d4',
                        fillOpacity: 0.08
                    }
                }).addTo(map);

                if (boundaryLayer.getBounds().isValid()) {
                    map.fitBounds(boundaryLayer.getBounds(), { padding: [30, 30], maxZoom: 13, animate: true });
                }
                mapTargetLabel.textContent = `対象自治体: ${areaTitle} (位置クローズアップ完了)`;
                progressText.textContent = `${areaTitle} の選択完了。処理を実行できます。`;
            })
            .catch(err => {
                console.log('Boundary zoom skipped:', err);
                mapTargetLabel.textContent = `対象自治体: ${areaTitle}`;
                progressText.textContent = `${areaTitle} の選択完了。`;
            })
            .finally(() => {
                prefSelect.disabled = false;
                citySelect.disabled = false;
                btnStart.disabled = false;
            });
    }

    // 知識データベース (解説用モーダル表示データ)
    const ANALYSIS_KNOWLEDGE = {
        slope: {
            title: "傾斜角 (Slope Map)",
            icon: "📐",
            category: "地形幾何学・傾斜解析",
            output: "GeoTIFF (.tif) [単位: 度 (°)]",
            description: "DEM標高格子データの各セルにおける水平・垂直方向の標高差（勾配ベクトル）から、地表の傾斜角度（0°〜90°）を算出します。",
            formula: "Slope = arctan( sqrt( (dz/dx)^2 + (dz/dy)^2 ) ) * (180 / π)",
            applications: [
                "土砂災害・地すべり危険傾斜地（30°〜45°）のスクリーニング",
                "森林作業道・林道の開設に適した緩傾斜線の特定",
                "農地・造成地・土木施工における勾配判定"
            ]
        },
        aspect: {
            title: "斜面方位 (Aspect Map)",
            icon: "🧭",
            category: "日照・微気象解析",
            output: "GeoTIFF (.tif) [単位: 度 (0°~360°, 北=0°)]",
            description: "斜面が東西南北のどの方向を向いているかを計算します。太陽光の照射角度や季節ごとの日照時間、微気象に直結します。",
            formula: "Aspect = mod(90° - arctan2(dz/dy, -dz/dx) * (180 / π), 360°)",
            applications: [
                "太陽光発電パネルの設置に最適な南向き斜面の抽出",
                "積雪・雪解け速度の地域的シミュレーション",
                "樹木・植生の自生分布や陽樹・陰樹の環境判定"
            ]
        },
        hillshade: {
            title: "陰影起伏 (Hillshade Map)",
            icon: "☀️",
            category: "視覚化・地形可視化",
            output: "GeoTIFF (.tif) [輝度: 0-255]",
            description: "仮想的な太陽光源（デフォルト: 方位角315°、高度45°）を設定し、地形の法線ベクトルとの内積から立体的な影を計算描画します。",
            formula: "Hillshade = 255 * (cos(Zenith) * cos(Slope) + sin(Zenith) * sin(Slope) * cos(Azimuth - Aspect))",
            applications: [
                "2D背景地図への重畳による高度な立体地形描画",
                "活断層・リニアメント・地すべり崖の目視判読",
                "航空写真・衛星画像の手法比較と地形認識強化"
            ]
        },
        curvature: {
            title: "地形曲率 (Curvature Map)",
            icon: "〰️",
            category: "水文・地形微形態",
            output: "GeoTIFF (.tif) [正: 尾根, 負: 谷]",
            description: "標高曲面の2次微分（ラプラシアン）を計算し、地表の凹凸状況を数値化します。正の数値は周囲より張り出した尾根、負の数値は窪んだ谷筋を示します。",
            formula: "Curvature = ∇²z = (d²z / dx²) + (d²z / dy²)",
            applications: [
                "雨水・表面流出水が集中する潜在的な谷筋（水路）の自動特定",
                "尾根筋・山頂地形の自動抽出",
                "表層崩壊・土砂流出が起きやすい集水窪地の判定"
            ]
        },
        csmap: {
            title: "CS立体図 (CS Map)",
            icon: "🗺️",
            category: "日本発・高度微地形表現",
            output: "RGBカラー GeoTIFF (.tif) [3チャンネル 8bit]",
            description: "長野県林業総合センターが開発した高度地形表現手法。標高曲率（凸部＝赤、凹部＝青）と傾斜角（輝度）をカラー合成し、森林下でも微地形を鮮明に浮き立たせます。",
            formula: "R: 尾根曲率(赤) + 輝度, G: 傾斜逆転(緑), B: 谷曲率(青) + 輝度",
            applications: [
                "樹木に隠れた古道・山城跡・崩壊痕・微地形の発見",
                "地すべり移動体・崖・危険個所の精密地形判読",
                "現地踏査前の高精度作業道設計"
            ]
        },
        twi: {
            title: "地形湿潤指数 (TWI: Topographic Wetness Index)",
            icon: "💧",
            category: "水文・土壌環境解析",
            output: "GeoTIFF (.tif) [無次元指数]",
            description: "上流からの集水面積（a）と斜面傾斜（tan β）の比率から、水分の集積しやすさ・湿潤度を算出します。",
            formula: "TWI = ln( a / tan(β) )",
            applications: [
                "雨天時に泥濘（でいねい）化しやすい林道・作業道の予測",
                "湧水ポイント・地下水涵養域の特定",
                "湿地性植物の生育適地や湿潤土壌の分布推定"
            ]
        },
        viewshed: {
            title: "可視領域解析 (Viewshed Map)",
            icon: "👁️",
            category: "景観・視認性解析",
            output: "GeoTIFF (.tif) [1: 可視, 0: 視蔽]",
            description: "特定観測点（標高＋視線高2m）から、周辺の山や尾根による遮蔽を計算し、直接見通せる視界範囲を解析します。",
            formula: "Line-of-Sight Raycasting (Elevation Angle vs Distance Comparison)",
            applications: [
                "無線通信タワー・基地局の電波カバーエリア推定",
                "風力発電・太陽光発電施設の景観影響評価",
                "避難所・監視カメラ・展望台の見通し範囲調査"
            ]
        }
    };

    // ヘルプボタン モーダル発出イベントの設定
    document.querySelectorAll('.help-btn').forEach(btn => {
        btn.addEventListener('click', (e) => {
            e.preventDefault();
            const techKey = btn.getAttribute('data-tech');
            const data = ANALYSIS_KNOWLEDGE[techKey];
            if (!data) return;

            document.getElementById('modal-icon').textContent = data.icon;
            document.getElementById('modal-title').textContent = data.title;
            document.getElementById('modal-category').textContent = data.category;
            document.getElementById('modal-output').textContent = data.output;
            document.getElementById('modal-description').textContent = data.description;
            document.getElementById('modal-formula').textContent = data.formula;

            const appList = document.getElementById('modal-applications');
            appList.innerHTML = '';
            data.applications.forEach(appText => {
                const li = document.createElement('li');
                li.textContent = `• ${appText}`;
                appList.appendChild(li);
            });

            document.getElementById('help-modal').style.display = 'flex';
        });
    });

    const helpModal = document.getElementById('help-modal');
    const modalCloseBtn = document.getElementById('modal-close-btn');

    modalCloseBtn.addEventListener('click', () => {
        helpModal.style.display = 'none';
    });

    helpModal.addEventListener('click', (e) => {
        if (e.target === helpModal) {
            helpModal.style.display = 'none';
        }
    });

    // 4. パイプライン実行
    btnStart.addEventListener('click', () => {
        if (!currentPref || !prefSelect.value) {
            alert('都道府県を選択してください。');
            return;
        }

        const selectedCode = currentPref.code;
        const selectedCity = citySelect.value || 'ALL';
        
        const chkSlope = document.getElementById('chk-slope').checked;
        const chkAspect = document.getElementById('chk-aspect').checked;
        const chkHillshade = document.getElementById('chk-hillshade').checked;
        const chkCurvature = document.getElementById('chk-curvature').checked;
        const chkCsmap = document.getElementById('chk-csmap').checked;
        const chkTwi = document.getElementById('chk-twi').checked;
        const chkViewshed = document.getElementById('chk-viewshed').checked;

        btnStart.style.display = 'none';
        btnCancel.style.display = 'block';
        btnCancel.disabled = false;
        updateStatus('running', '実行中');
        clearLogs();
        resetSteps();
        clearAllMapLayers(true);

        const areaLabel = (selectedCity === 'ALL') ? `${currentPref.name}全域` : `${currentPref.name} ${selectedCity}`;
        logMessage(`=== ${areaLabel}（DEM解像度: ${selectedResolution}）の多角GIS構築を開始します ===`, 'system');
        updateProgress(5, 'タスク起動中...');

        let url = `/api/process/${selectedCode}?resolution=${selectedResolution}` +
                  `&generate_slope=${chkSlope}` +
                  `&aspect=${chkAspect}` +
                  `&hillshade=${chkHillshade}` +
                  `&curvature=${chkCurvature}` +
                  `&csmap=${chkCsmap}` +
                  `&twi=${chkTwi}` +
                  `&viewshed=${chkViewshed}`;

        if (selectedCity !== 'ALL') {
            url += `&city_name=${encodeURIComponent(selectedCity)}`;
        }

        fetch(url, { method: 'POST' })
            .then(res => {
                if (!res.ok) {
                    return res.json().then(err => { throw new Error(err.detail || 'タスク起動失敗'); });
                }
                return res.json();
            })
            .then(data => {
                logMessage(`タスク起動成功: ${data.message}`, 'system');
                startMonitoring();
            })
            .catch(err => {
                logMessage(`エラー: ${err.message || err}`, 'error');
                updateStatus('error', 'エラー');
                resetButtons();
            });
    });


    btnCancel.addEventListener('click', () => {
        btnCancel.disabled = true;
        logMessage('⚠️ 処理中止を要求しています...', 'warning');

        fetch('/api/cancel', { method: 'POST' })
            .then(res => res.json())
            .then(data => {
                logMessage(`中止シグナル送信完了: ${data.message}`, 'warning');
            })
            .catch(err => {
                logMessage(`中止シグナル送信エラー: ${err}`, 'error');
                btnCancel.disabled = false;
            });
    });

    function resetButtons() {
        btnStart.style.display = 'block';
        btnStart.disabled = false;
        btnCancel.style.display = 'none';
        btnCancel.disabled = false;
    }

    function startMonitoring() {
        if (pollTimer) clearInterval(pollTimer);
        pollTimer = setInterval(pollStatus, 1000);

        if (eventSource) eventSource.close();
        eventSource = new EventSource('/api/stream-logs');

        eventSource.onmessage = (e) => {
            try {
                const data = JSON.parse(e.data);
                if (data.msg) {
                    logMessage(data.msg);
                    updateProgress(data.pct, data.msg);
                    updateStepIndicator(data.pct);

                    if (data.msg.includes('図郭数:') || data.pct >= 15) {
                        tryLoadLiveZukakuAnimation();
                    }
                }
            } catch (err) {}
        };
    }

    function pollStatus() {
        fetch('/api/status')
            .then(res => res.json())
            .then(data => {
                if (!data) return;

                if (data.status === 'running') {
                    updateStatus('running', '実行中');
                    if (data.current_message) {
                        updateProgress(data.progress || 10, data.current_message);
                        updateStepIndicator(data.progress || 10);
                    }
                } else if (data.status === 'completed') {
                    stopMonitoring();
                    updateStatus('completed', '完了');
                    updateProgress(100, '[OK] 処理完了！');
                    updateStepIndicator(100);
                    resetButtons();
                    showResult(data.result);
                } else if (data.status === 'canceled') {
                    stopMonitoring();
                    updateStatus('canceled', '中止');
                    updateProgress(data.progress || 0, '⛔ 処理が中止されました');
                    logMessage('処理が正常に中止されました。', 'warning');
                    resetButtons();
                } else if (data.status === 'error') {
                    stopMonitoring();
                    updateStatus('error', 'エラー');
                    logMessage(`処理失敗: ${data.error}`, 'error');
                    resetButtons();
                }
            })
            .catch(err => console.error('Poll error:', err));
    }

    function tryLoadLiveZukakuAnimation() {
        if (animatedFeatureIds.size > 0) return;

        let url = `/api/preview/${currentPref.code}`;
        if (currentCity && currentCity !== 'ALL') {
            url += `?city_name=${encodeURIComponent(currentCity)}`;
        }

        fetch(url)
            .then(res => {
                if (!res.ok) throw new Error('Not ready');
                return res.json();
            })
            .then(geojson => {
                const features = geojson.features || [];
                if (features.length === 0) return;

                if (!liveZukakuLayerGroup) {
                    liveZukakuLayerGroup = L.layerGroup().addTo(map);
                }

                mapTargetLabel.textContent = `可視化: 1/2,500 公共図郭メッシュ描画中 (${features.length} 区画)`;

                let idx = 0;
                if (animTimer) clearInterval(animTimer);

                animTimer = setInterval(() => {
                    if (idx >= features.length) {
                        clearInterval(animTimer);
                        return;
                    }
                    const feat = features[idx];
                    const zCode = feat.properties ? feat.properties.code || feat.properties.zukaku_code : idx;
                    animatedFeatureIds.add(zCode);

                    const layer = L.geoJSON(feat, {
                        style: {
                            color: '#06b6d4',
                            weight: 1.5,
                            fillColor: '#0891b2',
                            fillOpacity: 0.25
                        }
                    });
                    liveZukakuLayerGroup.addLayer(layer);
                    idx++;
                }, 15);

                const fullGeojsonLayer = L.geoJSON(geojson);
                if (fullGeojsonLayer.getBounds().isValid()) {
                    map.fitBounds(fullGeojsonLayer.getBounds(), { padding: [30, 30], animate: true });
                }
            })
            .catch(err => {});
    }

    function stopMonitoring() {
        if (pollTimer) clearInterval(pollTimer);
        if (eventSource) eventSource.close();
        if (animTimer) clearInterval(animTimer);
    }

    function clearAllMapLayers(keepBoundary = false) {
        if (!keepBoundary && boundaryLayer) {
            map.removeLayer(boundaryLayer);
            boundaryLayer = null;
        }
        if (liveZukakuLayerGroup) {
            map.removeLayer(liveZukakuLayerGroup);
            liveZukakuLayerGroup = null;
        }
        animatedFeatureIds.clear();
        if (animTimer) clearInterval(animTimer);
    }

    function updateStepIndicator(pct) {
        for (let i = 1; i <= 4; i++) {
            const el = document.getElementById(`step-${i}`);
            if (el) el.classList.remove('active', 'done');
        }

        const s1 = document.getElementById('step-1');
        const s2 = document.getElementById('step-2');
        const s3 = document.getElementById('step-3');
        const s4 = document.getElementById('step-4');

        if (pct >= 10 && s1) s1.classList.add('done');
        else if (s1) s1.classList.add('active');

        if (pct >= 70 && s2) s2.classList.add('done');
        else if (pct >= 10 && s2) s2.classList.add('active');

        if (pct >= 90 && s3) s3.classList.add('done');
        else if (pct >= 70 && s3) s3.classList.add('active');

        if (pct >= 100 && s4) s4.classList.add('done');
        else if (pct >= 90 && s4) s4.classList.add('active');
    }

    function resetSteps() {
        for (let i = 1; i <= 4; i++) {
            const el = document.getElementById(`step-${i}`);
            if (el) el.classList.remove('active', 'done');
        }
    }

    function updateProgress(pct, msg) {
        progressFill.style.width = `${pct}%`;
        progressPct.textContent = `${pct}%`;
        progressText.textContent = msg || '';
    }

    function updateStatus(state, label) {
        statusBadge.className = `status-indicator ${state}`;
        statusBadge.textContent = label;
    }

    function logMessage(msg, type = '') {
        const div = document.createElement('div');
        div.className = `log-entry ${type}`;
        if (msg.includes('[OK]') || msg.includes('成功') || msg.includes('完了')) div.classList.add('success');
        if (msg.includes('エラー') || msg.includes('失敗')) div.classList.add('error');
        if (msg.includes('⚠️') || msg.includes('⛔')) div.classList.add('warning');
        div.textContent = `[${new Date().toLocaleTimeString()}] ${msg}`;
        logWindow.appendChild(div);
        logWindow.scrollTop = logWindow.scrollHeight;
    }

    function clearLogs() {
        logWindow.innerHTML = '';
    }

    function showResult(result) {
        let dlUrl = `/api/download/${currentPref.code}`;
        if (currentCity && currentCity !== 'ALL') {
            dlUrl += `?city_name=${encodeURIComponent(currentCity)}`;
        }
        btnDownloadZip.href = dlUrl;
        btnDownloadZip.classList.remove('disabled');

        const summary = (result && result.summary) ? result.summary : {};
        statZukaku.textContent = (summary.total_zukaku || 0).toLocaleString();
        statResolution.textContent = summary.resolution || selectedResolution;
        
        if (summary.min_elevation_m !== undefined && summary.max_elevation_m !== undefined) {
            statElevationRange.textContent = `${summary.min_elevation_m}m ~ ${summary.max_elevation_m}m`;
        } else {
            statElevationRange.textContent = '-';
        }
        
        statMeanElevation.textContent = (summary.mean_elevation_m !== undefined) ? `${summary.mean_elevation_m} m` : '-';

        const genContainer = document.getElementById('generated-layers-container');
        const genList = document.getElementById('generated-layers-list');
        if (genContainer && genList) {
            genList.innerHTML = '';
            let layerCount = 0;

            const createDlBadge = (filename, icon = '🗺️') => {
                const a = document.createElement('a');
                let singleDlUrl = `/api/download-file/${currentPref.code}/${encodeURIComponent(filename)}`;
                if (currentCity && currentCity !== 'ALL') {
                    singleDlUrl += `?city_name=${encodeURIComponent(currentCity)}`;
                }
                a.href = singleDlUrl;
                a.target = '_blank';
                a.className = 'layer-badge clickable';
                a.title = 'クリックして個別にダウンロード';
                a.innerHTML = `${icon} ${filename} <span>⬇️</span>`;
                return a;
            };

            if (summary.dem_geotiff) {
                genList.appendChild(createDlBadge(summary.dem_geotiff, '📄'));
                layerCount++;
            }
            if (summary.generated_layers) {
                Object.values(summary.generated_layers).forEach(layerName => {
                    genList.appendChild(createDlBadge(layerName, '🗺️'));
                    layerCount++;
                });
            }
            genContainer.style.display = (layerCount > 0) ? 'block' : 'none';
        }


        loadMapPreview(currentPref.code, currentCity);
    }


    function initMap() {
        if (map) return;
        map = L.map('map').setView([36.5, 137.5], 5.5);
        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
            maxZoom: 18,
            attribution: '© OpenStreetMap contributors | 地理院タイル'
        }).addTo(map);

        const legend = L.control({ position: 'bottomright' });
        legend.onAdd = function () {
            const div = L.DomUtil.create('div', 'map-legend');
            div.innerHTML = `
                <div class="legend-title">地図表示凡例</div>
                <div class="legend-item"><span class="legend-color" style="background:#06b6d4;"></span> <b>対象領域 / 行政境界</b></div>
                <div class="legend-item"><span class="legend-color" style="background:#0891b2; opacity:0.6;"></span> <b>1/2,500 公共図郭</b></div>
                <div class="legend-item"><span class="legend-color" style="background:#10b981;"></span> <b>DEM (5m/10m) 解析済</b></div>
            `;
            return div;
        };
        legend.addTo(map);
    }

    function loadMapPreview(code, city) {
        initMap();
        let previewUrl = `/api/preview/${code}`;
        if (city && city !== 'ALL') {
            previewUrl += `?city_name=${encodeURIComponent(city)}`;
        }

        fetch(previewUrl)
            .then(res => {
                if (!res.ok) throw new Error('Preview not ready');
                return res.json();
            })
            .then(geojson => {
                clearAllMapLayers(true);

                const finalLayer = L.geoJSON(geojson, {
                    style: {
                        color: '#059669',
                        weight: 1.5,
                        fillColor: '#10b981',
                        fillOpacity: 0.35
                    },
                    onEachFeature: (feature, layer) => {
                        const props = feature.properties;
                        let popupHtml = `<b>図郭コード: ${props.code || props.zukaku_code}</b><br>`;
                        popupHtml += `図郭区分: 1/2,500 公共測量図郭<br>`;
                        popupHtml += `DEMフォーマット: GeoTIFF (.tif)<br>`;
                        layer.bindPopup(popupHtml);
                    }
                }).addTo(map);

                const areaTitle = (city && city !== 'ALL') ? `${currentPref.name} ${city}` : `${currentPref.name} 全域`;
                mapTargetLabel.textContent = `成果物プレビュー: ${areaTitle} (全 ${geojson.features ? geojson.features.length : 0} 図郭)`;

                if (finalLayer.getBounds().isValid()) {
                    map.fitBounds(finalLayer.getBounds(), { padding: [30, 30], animate: true });
                }
            })
            .catch(err => console.log('Map final preview note:', err.message));
    }
});
