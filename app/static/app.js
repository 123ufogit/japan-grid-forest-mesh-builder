// JavaScript for Japan GIS Pipeline Dashboard (With Map Legend & Persistent Boundary Overlay)

document.addEventListener('DOMContentLoaded', () => {
    let prefectures = [];
    let currentPref = null;
    let currentCity = 'ALL';
    let map = null;
    let boundaryLayer = null;
    let liveZukakuLayerGroup = null;
    let animatedFeatureIds = new Set();
    let eventSource = null;
    let pollTimer = null;
    let animTimer = null;

    // Elements
    const prefSelect = document.getElementById('pref-select');
    const citySelect = document.getElementById('city-select');
    const infoName = document.getElementById('info-pref-name');
    const infoSystem = document.getElementById('info-system');
    const infoEpsg = document.getElementById('info-epsg');
    const infoTargetArea = document.getElementById('info-target-area');

    const btnStart = document.getElementById('btn-start');
    const btnCancel = document.getElementById('btn-cancel');
    const statusBadge = document.getElementById('status-badge');
    const progressFill = document.getElementById('progress-fill');
    const progressText = document.getElementById('progress-text');
    const progressPct = document.getElementById('progress-pct');
    const logWindow = document.getElementById('log-window');

    const btnDownloadZip = document.getElementById('btn-download-zip');
    const statZukaku = document.getElementById('stat-zukaku');
    const statMesh = document.getElementById('stat-mesh');
    const statForestHa = document.getElementById('stat-forest-ha');
    const statArtificialPct = document.getElementById('stat-人工林率');
    const mapTargetLabel = document.getElementById('map-target-label');

    // 1. マップ初期化 (初期状態：日本列島全体俯瞰)
    initMap();

    // 2. 都道府県一覧の取得
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
        // 初期状態は未選択にする
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

            // 前の都道府県の市町村選択肢を完全リセット＆最新市町村取得
            fetchMunicipalities(currentPref.code);
        }
    }

    // 都道府県選択変更時に市町村リストを【完全クリア・リセット】する関数
    function fetchMunicipalities(prefCode) {
        citySelect.disabled = true;
        citySelect.innerHTML = '<option value="ALL">⏳ 市町村リストを読み込み中... お待ちください</option>';
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

    // 自治体・都道府県選択時に自動クローズアップする関数
    function zoomToBoundary(prefCode, city) {
        initMap();
        const areaTitle = (city && city !== 'ALL') ? `${currentPref.name} ${city}` : `${currentPref.name} 全域`;
        
        // ★新しい自治体が選択されたら前の自治体境界 GeoJSON を確実に消去★
        if (boundaryLayer) {
            map.removeLayer(boundaryLayer);
            boundaryLayer = null;
        }

        // ⏳ ロード中メッセージの表示
        mapTargetLabel.innerHTML = `⏳ ${areaTitle} の位置データを取得・ズーム調整中... 少々お待ちください`;
        progressText.textContent = `⏳ ${areaTitle} の境界データを読み込み中... お待ちください`;
        prefSelect.disabled = true;
        citySelect.disabled = true;
        btnStart.disabled = true;

        let url = `/api/boundary-polygon/${prefCode}`;
        if (city && city !== 'ALL') {
            url += `?city_name=${encodeURIComponent(city)}`;
        }

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

    // 3. パイプライン実行トリガー
    btnStart.addEventListener('click', () => {
        if (!currentPref || !prefSelect.value) {
            alert('都道府県を選択してください。');
            return;
        }

        const selectedCode = currentPref.code;
        const selectedCity = citySelect.value || 'ALL';

        btnStart.style.display = 'none';
        btnCancel.style.display = 'block';
        btnCancel.disabled = false;
        updateStatus('running', '実行中');
        clearLogs();
        resetSteps();
        clearAllMapLayers(true); // 境界 GeoJSON は継続保持

        const areaLabel = (selectedCity === 'ALL') ? `${currentPref.name}全域` : `${currentPref.name} ${selectedCity}`;
        logMessage(`=== ${areaLabel}（第${currentPref.system}系, EPSG:${currentPref.epsg}）の構築を開始します ===`, 'system');
        updateProgress(5, 'タスク起動中...');

        let url = `/api/process/${selectedCode}`;
        if (selectedCity !== 'ALL') {
            url += `?city_name=${encodeURIComponent(selectedCity)}`;
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

                    // 1/2,500 図郭抽出ログや地区完了ログに連動して順次アニメーション描画
                    if (data.msg.includes('図郭数:') || data.pct >= 15) {
                        tryLoadLiveZukakuAnimation();
                    }
                    if (data.msg.includes('20mメッシュ GPKG 作成完了')) {
                        highlightDistrictAnimation(data.msg);
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

    // 順次パラパラと描画するシーケンシャル・アニメーションエンジン
    function tryLoadLiveZukakuAnimation() {
        if (animatedFeatureIds.size > 0) return; // 既に開始済み

        let url = `/api/live-zukaku/${currentPref.code}`;
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

                mapTargetLabel.textContent = `リアルタイム可視化: 図郭メッシュ順次描画中 (${features.length} 区画)`;

                // 20ms 間隔で図郭ポリゴンをパラパラとアニメーション描画
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
                            color: '#059669',
                            weight: 1.5,
                            fillColor: '#10b981',
                            fillOpacity: 0.35
                        }
                    });
                    liveZukakuLayerGroup.addLayer(layer);
                    idx++;
                }, 20);

                const fullGeojsonLayer = L.geoJSON(geojson);
                if (fullGeojsonLayer.getBounds().isValid()) {
                    map.fitBounds(fullGeojsonLayer.getBounds(), { padding: [30, 30], animate: true });
                }
            })
            .catch(err => {});
    }

    function highlightDistrictAnimation(msg) {
        if (!liveZukakuLayerGroup) return;
        // 地区完了時に発光エフェクト
        liveZukakuLayerGroup.eachLayer(layer => {
            layer.setStyle({ color: '#34d399', fillColor: '#10b981', fillOpacity: 0.5, weight: 2 });
        });
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

        if (pct >= 45 && s2) s2.classList.add('done');
        else if (pct >= 10 && s2) s2.classList.add('active');

        if (pct >= 85 && s3) s3.classList.add('done');
        else if (pct >= 45 && s3) s3.classList.add('active');

        if (pct >= 100 && s4) s4.classList.add('done');
        else if (pct >= 85 && s4) s4.classList.add('active');
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
        statMesh.textContent = (summary.total_mesh || 0).toLocaleString();
        statForestHa.textContent = `${(summary.total_forest_ha || 0).toLocaleString()} ha`;
        statArtificialPct.textContent = `${summary.avg_人工林率 || 0} %`;

        loadMapPreview(currentPref.code, currentCity);
    }

    function initMap() {
        if (map) return;
        map = L.map('map').setView([36.5, 137.5], 5.5); // 初期表示：日本全域
        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
            maxZoom: 18,
            attribution: '© OpenStreetMap contributors'
        }).addTo(map);

        // ★「20mメッシュ情報」凡例コントロールの追加★
        const legend = L.control({ position: 'bottomright' });
        legend.onAdd = function () {
            const div = L.DomUtil.create('div', 'map-legend');
            div.innerHTML = `
                <div class="legend-title">20mメッシュ情報 凡例</div>
                <div class="legend-item"><span class="legend-color" style="background:#10b981;"></span> <b>取得</b> (全域データ取得)</div>
                <div class="legend-item"><span class="legend-color" style="background:#f59e0b;"></span> <b>一部取得</b> (一部データ取得)</div>
                <div class="legend-item"><span class="legend-color" style="background:#6b7280;"></span> <b>未取得</b> (データ無し)</div>
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
                clearAllMapLayers(true); // ★境界 GeoJSON は継続表示★

                const finalLayer = L.geoJSON(geojson, {
                    style: (feature) => {
                        const status20m = feature.properties['20mメッシュ情報'] || '未取得';
                        let color = '#6b7280'; // 未取得: グレー
                        let strokeColor = '#4b5563';
                        let opacity = 0.25;

                        if (status20m === '取得') {
                            color = '#10b981'; // 取得: エメラルドグリーン
                            strokeColor = '#059669';
                            opacity = 0.45;
                        } else if (status20m === '一部取得') {
                            color = '#f59e0b'; // 一部取得: アンバーオレンジ
                            strokeColor = '#d97706';
                            opacity = 0.45;
                        }

                        return {
                            color: strokeColor,
                            weight: 1.5,
                            fillColor: color,
                            fillOpacity: opacity
                        };
                    },
                    onEachFeature: (feature, layer) => {
                        const props = feature.properties;
                        const status20m = props['20mメッシュ情報'] || '未取得';
                        let badgeColor = '#6b7280';
                        if (status20m === '取得') badgeColor = '#10b981';
                        else if (status20m === '一部取得') badgeColor = '#f59e0b';

                        let popupHtml = `<b>図郭コード: ${props.zukaku_code}</b><br>`;
                        popupHtml += `<span style="background:${badgeColor}; color:#000; padding:2px 6px; border-radius:4px; font-weight:bold; font-size:0.75rem;">20mメッシュ情報: ${status20m}</span><hr style="margin:6px 0;">`;
                        popupHtml += `天然林: ${props['天然林'] || 0} ha<br>`;
                        popupHtml += `人工林: ${props['人工林'] || 0} ha<br>`;
                        popupHtml += `無林木地: ${props['無林木地'] || 0} ha<br>`;
                        popupHtml += `<b>総森林面積: ${props['合計'] || 0} ha</b><br>`;
                        popupHtml += `<b>人工林率: ${props['人工林率'] || 0} %</b>`;
                        layer.bindPopup(popupHtml);
                    }
                }).addTo(map);

                const areaTitle = (city && city !== 'ALL') ? `${currentPref.name} ${city}` : `${currentPref.name} 全域`;
                mapTargetLabel.textContent = `最終成果物プレビュー: ${areaTitle} (全 ${geojson.features ? geojson.features.length : 0} 区画)`;

                if (finalLayer.getBounds().isValid()) {
                    map.fitBounds(finalLayer.getBounds(), { padding: [30, 30], animate: true });
                }
            })
            .catch(err => console.log('Map final preview note:', err.message));
    }
});
