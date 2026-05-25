const API = "";

let products = [];
let chartViews = null;
let chartLikes = null;

async function loadProducts() {
  try {
    const res = await fetch(`${API}/api/products`);
    products = await res.json();
    renderTable(products);
    renderCharts(products);
  } catch (err) {
    console.error("Ошибка при получении товаров:", err);
  }
}

function renderTable(list) {
  const tbody = document.getElementById("table-body");
  tbody.innerHTML = "";

  list.forEach((p) => {
    const tr = document.createElement("tr");
    tr.innerHTML = `
            <td>${p.id}</td>
            <td>${p.name}</td>
            <td>${p.category}</td>
            <td>${p.views}</td>
            <td>${p.likes}</td>
        `;
    tbody.appendChild(tr);
  });
}

function renderCharts(list) {
  const byViews = list
    .slice()
    .sort((a, b) => b.views - a.views)
    .slice(0, 7);

  const byLikes = list
    .slice()
    .sort((a, b) => b.likes - a.likes)
    .slice(0, 7);

  if (chartViews) chartViews.destroy();
  if (chartLikes) chartLikes.destroy();

  chartViews = new Chart(document.getElementById("chart-views"), {
    type: "bar",
    data: {
      labels: byViews.map((p) => p.name),
      datasets: [
        {
          label: "Просмотры",
          data: byViews.map((p) => p.views),
          backgroundColor: "#1565c0",
        },
      ],
    },
    options: {
      responsive: true,
      plugins: {
        legend: { display: false },
      },
    },
  });

  chartLikes = new Chart(document.getElementById("chart-likes"), {
    type: "bar",
    data: {
      labels: byLikes.map((p) => p.name),
      datasets: [
        {
          label: "Лайки",
          data: byLikes.map((p) => p.likes),
          backgroundColor: "#e53935",
        },
      ],
    },
    options: {
      responsive: true,
      plugins: {
        legend: { display: false },
      },
    },
  });
}

async function sendLike() {
  const idInput = document.getElementById("like-id");
  const id = idInput.value.trim();
  const result = document.getElementById("like-result");

  if (!id) {
    result.style.color = "red";
    result.textContent = "Введите ID товара!";
    return;
  }

  try {
    const res = await fetch(`${API}/api/products/${id}/like`, {
      method: "POST",
    });

    if (res.ok) {
      const p = await res.json();
      result.style.color = "green";
      result.textContent = `Лайк поставлен! Товар: ${p.name} — теперь ${p.likes} лайков.`;
      idInput.value = "";
      loadProducts();
    } else {
      result.style.color = "red";
      result.textContent = `Товар с ID ${id} не найден.`;
    }
  } catch (err) {
    result.style.color = "red";
    result.textContent = "Ошибка сети при отправке лайка.";
  }
}

loadProducts();
