const API = "";

let products = [];
let chartViews = null;
let chartLikes = null;

var socket = null;
var pc = null;
var dataChannel = null;

function initWebRTC() {
    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const roomId = "dashboard-sync";
    socket = new WebSocket(`${protocol}//${window.location.host}/ws/${roomId}`);

    pc = new RTCPeerConnection({ iceServers: [{ urls: "stun:stun.l.google.com:19302" }] });

    pc.onicecandidate = function(event) {
        if (event.candidate) {
            socket.send(JSON.stringify({ candidate: event.candidate }));
        }
    };

    pc.ondatachannel = function(event) {
        dataChannel = event.channel;
        setupDataChannel(dataChannel);
    };

    socket.onmessage = function(event) {
        var data = JSON.parse(event.data);

        if (data.type === "peer-joined") {
            dataChannel = pc.createDataChannel("dashboard-sync");
            setupDataChannel(dataChannel);

            pc.createOffer().then(function(offer) {
                return pc.setLocalDescription(offer);
            }).then(function() {
                socket.send(JSON.stringify({ sdp: pc.localDescription }));
            });

        } else if (data.sdp) {
            pc.setRemoteDescription(new RTCSessionDescription(data.sdp)).then(function() {
                if (data.sdp.type === "offer") {
                    pc.createAnswer().then(function(answer) {
                        return pc.setLocalDescription(answer);
                    }).then(function() {
                        socket.send(JSON.stringify({ sdp: pc.localDescription }));
                    });
                }
            });
        } else if (data.candidate) {
            pc.addIceCandidate(new RTCIceCandidate(data.candidate));
        }
    };

    socket.onopen = function() {
        setRtcStatus("connecting", "WebRTC: ожидание второго участника...");
        socket.send(JSON.stringify({ type: "peer-joined" }));
    };

    socket.onclose = function() {
        setRtcStatus("offline", "WebRTC: не подключён");
    };
}

function setupDataChannel(channel) {
    channel.onopen = function() {
        setRtcStatus("synced", "WebRTC: синхронизирован ✓");
    };
    channel.onclose = function() {
        setRtcStatus("connecting", "WebRTC: соединение потеряно...");
    };
    channel.onmessage = function(e) {
        var msg = JSON.parse(e.data);

        if (msg.type === "filter-change") {
            var dropdown = document.getElementById("category-filter");
            dropdown.value = msg.category;
            applyFilter(false);

        } else if (msg.type === "data-reload") {
            loadProducts(false);
        }
    };
}

function broadcastEvent(obj) {
    if (dataChannel && dataChannel.readyState === "open") {
        dataChannel.send(JSON.stringify(obj));
    }
}

function setRtcStatus(state, label) {
    var dot = document.getElementById("rtc-dot");
    var lbl = document.getElementById("rtc-label");
    dot.className = "rtc-dot " + state;
    lbl.textContent = label;
}

async function loadProducts(broadcast = false) {
    try {
        const res = await fetch(`${API}/api/products`);
        products = await res.json();
        populateCategoryDropdown(products);
        applyFilter(false);
        if (broadcast) {
            broadcastEvent({ type: "data-reload" });
        }
    } catch (err) {
        console.error("Ошибка при получении товаров:", err);
    }
}

function populateCategoryDropdown(list) {
    const filter = document.getElementById("category-filter");
    const current = filter.value;
    const categories = [...new Set(list.map(p => p.category))];

    filter.innerHTML = '<option value="all">Все категории</option>';
    categories.forEach(cat => {
        const option = document.createElement("option");
        option.value = cat;
        option.textContent = cat;
        filter.appendChild(option);
    });

    if (categories.includes(current)) {
        filter.value = current;
    }
}

function onFilterChange() {
    const category = document.getElementById("category-filter").value;
    applyFilter(true);
    broadcastEvent({ type: "filter-change", category });
}

function applyFilter(doBroadcast = false) {
    const selectedCategory = document.getElementById("category-filter").value;
    let filtered = products;
    if (selectedCategory !== "all") {
        filtered = products.filter(p => p.category === selectedCategory);
    }
    renderTable(filtered);
    renderCharts(filtered);
}

function renderTable(list) {
    const tbody = document.getElementById("table-body");
    tbody.innerHTML = "";

    if (list.length === 0) {
        tbody.innerHTML = '<tr><td colspan="6" style="color:#888;text-align:center;">Нет товаров</td></tr>';
        return;
    }

    list.forEach((p) => {
        const tr = document.createElement("tr");
        tr.innerHTML = `
            <td>${p.id}</td>
            <td id="name-${p.id}">${p.name}</td>
            <td>${p.category}</td>
            <td>${p.views}</td>
            <td>${p.likes}</td>
            <td>
                <div class="actions-cell">
                    <button class="btn btn-orange btn-sm" onclick="promptRename(${p.id})">Переименовать</button>
                    <button class="btn btn-green btn-sm" onclick="promptPopularity(${p.id})">Популярность</button>
                    <button class="btn btn-red btn-sm" onclick="deleteProduct(${p.id})">Удалить</button>
                </div>
            </td>
        `;
        tbody.appendChild(tr);
    });
}

function renderCharts(list) {
    const byViews = list.slice().sort((a, b) => b.views - a.views).slice(0, 7);
    const byLikes = list.slice().sort((a, b) => b.likes - a.likes).slice(0, 7);

    if (chartViews) chartViews.destroy();
    if (chartLikes) chartLikes.destroy();

    chartViews = new Chart(document.getElementById("chart-views"), {
        type: "bar",
        data: {
            labels: byViews.map(p => p.name),
            datasets: [{ label: "Просмотры", data: byViews.map(p => p.views), backgroundColor: "#1565c0" }],
        },
        options: { responsive: true, plugins: { legend: { display: false } } },
    });

    chartLikes = new Chart(document.getElementById("chart-likes"), {
        type: "bar",
        data: {
            labels: byLikes.map(p => p.name),
            datasets: [{ label: "Лайки", data: byLikes.map(p => p.likes), backgroundColor: "#e53935" }],
        },
        options: { responsive: true, plugins: { legend: { display: false } } },
    });
}

async function createProduct() {
    const name = document.getElementById("new-name").value.trim();
    const category = document.getElementById("new-category").value.trim();
    const views = parseInt(document.getElementById("new-views").value) || 0;
    const likes = parseInt(document.getElementById("new-likes").value) || 0;
    const result = document.getElementById("op-result");

    if (!name || !category) {
        result.style.color = "red";
        result.textContent = "Введите название и категорию!";
        return;
    }

    try {
        const res = await fetch(`${API}/api/products`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ name, category, views, likes }),
        });
        if (res.ok) {
            const p = await res.json();
            result.style.color = "green";
            result.textContent = `✅ Товар "${p.name}" добавлен (id=${p.id})`;
            document.getElementById("new-name").value = "";
            document.getElementById("new-views").value = "0";
            document.getElementById("new-likes").value = "0";
            await loadProducts(true);
        } else {
            result.style.color = "red";
            result.textContent = "Ошибка создания товара.";
        }
    } catch (err) {
        result.style.color = "red";
        result.textContent = "Ошибка сети.";
    }
}

async function deleteProduct(id) {
    if (!confirm(`Удалить товар id=${id}?`)) return;
    try {
        const res = await fetch(`${API}/api/products/${id}`, { method: "DELETE" });
        if (res.status === 204) {
            await loadProducts(true);
        } else {
            alert("Не удалось удалить товар.");
        }
    } catch (err) {
        alert("Ошибка сети при удалении.");
    }
}

async function promptRename(id) {
    const current = document.getElementById(`name-${id}`)?.textContent || "";
    const newName = prompt(`Новое название для товара id=${id}:`, current);
    if (!newName || newName === current) return;

    try {
        const res = await fetch(`${API}/api/products/${id}`, {
            method: "PATCH",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ name: newName }),
        });
        if (res.ok) {
            await loadProducts(true);
        } else {
            alert("Не удалось переименовать товар.");
        }
    } catch (err) {
        alert("Ошибка сети.");
    }
}

async function promptPopularity(id) {
    const views = prompt(`Новое количество просмотров для товара id=${id}:`, "");
    if (views === null) return;
    const likes = prompt(`Новое количество лайков для товара id=${id}:`, "");
    if (likes === null) return;

    try {
        const res = await fetch(`${API}/api/products/${id}/popularity`, {
            method: "PUT",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                views: views !== "" ? parseInt(views) : null,
                likes: likes !== "" ? parseInt(likes) : null,
            }),
        });
        if (res.ok) {
            await loadProducts(true);
        } else {
            alert("Не удалось обновить популярность.");
        }
    } catch (err) {
        alert("Ошибка сети.");
    }
}

async function sendLike() {
    const idInput = document.getElementById("like-id");
    const id = idInput.value.trim();
    const result = document.getElementById("like-result");
    if (!id) { result.style.color = "red"; result.textContent = "Введите ID товара!"; return; }

    try {
        const res = await fetch(`${API}/api/products/${id}/like`, { method: "POST" });
        if (res.ok) {
            const p = await res.json();
            result.style.color = "green";
            result.textContent = `❤️ ${p.name}: ${p.likes} лайков`;
            idInput.value = "";
            await loadProducts(true);
        } else {
            result.style.color = "red";
            result.textContent = `Товар id=${id} не найден.`;
        }
    } catch (err) {
        result.style.color = "red";
        result.textContent = "Ошибка сети.";
    }
}

async function removeLike() {
    const idInput = document.getElementById("like-id");
    const id = idInput.value.trim();
    const result = document.getElementById("like-result");
    if (!id) { result.style.color = "red"; result.textContent = "Введите ID товара!"; return; }

    try {
        const res = await fetch(`${API}/api/products/${id}/like`, { method: "DELETE" });
        if (res.ok) {
            const p = await res.json();
            result.style.color = "green";
            result.textContent = `🗑 ${p.name}: ${p.likes} лайков`;
            idInput.value = "";
            await loadProducts(true);
        } else {
            result.style.color = "red";
            result.textContent = `Товар id=${id} не найден.`;
        }
    } catch (err) {
        result.style.color = "red";
        result.textContent = "Ошибка сети.";
    }
}

loadProducts(false);
initWebRTC();
