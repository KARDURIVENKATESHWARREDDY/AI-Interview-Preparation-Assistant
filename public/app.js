const CATEGORIES = ["Food", "Transport", "Shopping", "Bills", "Entertainment", "Health", "Education", "Other"];

let users = {};
let questions = [];
let currentUser = null;
let currentQuestion = null;

const $ = (id) => document.getElementById(id);


async function loadData() {
  const [u, q] = await Promise.all([
    fetch("/data/users.json").then((r) => r.json()),
    fetch("/data/questions.json").then((r) => r.json()),
  ]);
  users = u;
  questions = q;
}

function expenseKey(user) {
  return `expenses_${user}`;
}

function getExpenses(user) {
  return JSON.parse(localStorage.getItem(expenseKey(user)) || "[]");
}

function saveExpenses(user, list) {
  localStorage.setItem(expenseKey(user), JSON.stringify(list));
}

function nextExpenseId(list) {
  return list.length ? Math.max(...list.map((e) => e.id)) + 1 : 1;
}

function showLogin() {
  $("login-screen").classList.remove("hidden");
  $("app-screen").classList.add("hidden");
}

function showApp() {
  $("login-screen").classList.add("hidden");
  $("app-screen").classList.remove("hidden");
  $("user-label").textContent = `Signed in as ${currentUser}`;
  pickQuestion();
  renderExpenses("read");
}

function pickQuestion() {
  const pool = questions;
  currentQuestion = pool[Math.floor(Math.random() * pool.length)];
  $("q-meta").textContent = `${currentQuestion.category} · ${currentQuestion.difficulty}`;
  $("q-text").textContent = currentQuestion.question;
  $("feedback").classList.add("hidden");
}

async function submitAnswer() {
  const answer = $("answer").value.trim();
  if (!answer) return alert("Write an answer first.");
  $("feedback").classList.remove("hidden");
  $("feedback").textContent = "Analyzing…";
  try {
    const res = await fetch("/api/interview-feedback", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        question: currentQuestion.question,
        answer,
        category: currentQuestion.category,
      }),
    });
    const data = await res.json();
    $("feedback").textContent = data.text || data.error || "No response";
  } catch (e) {
    $("feedback").textContent = `Error: ${e.message}`;
  }
}

function renderExpenses(mode) {
  const list = getExpenses(currentUser);
  const total = list.reduce((s, e) => s + Number(e.amount), 0);
  $("exp-metrics").innerHTML = `
    <div class="metric"><span>Total</span><strong>$${total.toFixed(2)}</strong></div>
    <div class="metric"><span>Count</span><strong>${list.length}</strong></div>
  `;

  const el = $("exp-content");
  if (mode === "read") {
    if (!list.length) {
      el.innerHTML = "<p>No expenses. Add one in Create.</p>";
      return;
    }
    el.innerHTML = `<table><thead><tr><th>ID</th><th>Title</th><th>Amount</th><th>Category</th><th>Date</th></tr></thead><tbody>
      ${list.map((e) => `<tr><td>${e.id}</td><td>${e.title}</td><td>$${Number(e.amount).toFixed(2)}</td><td>${e.category}</td><td>${e.expense_date}</td></tr>`).join("")}
    </tbody></table>`;
    return;
  }

  if (mode === "create") {
    el.innerHTML = `
      <h3>Add expense</h3>
      <input id="c-title" placeholder="Title" />
      <input id="c-amount" type="number" step="0.01" placeholder="Amount" />
      <select id="c-cat">${CATEGORIES.map((c) => `<option>${c}</option>`).join("")}</select>
      <input id="c-date" type="date" value="${new Date().toISOString().slice(0, 10)}" />
      <button class="btn primary" id="c-save">Add</button>`;
    $("c-save").onclick = () => {
      const title = $("c-title").value.trim();
      const amount = parseFloat($("c-amount").value);
      if (!title || !(amount > 0)) return alert("Title and amount required.");
      const updated = [...list, {
        id: nextExpenseId(list),
        title,
        amount,
        category: $("c-cat").value,
        expense_date: $("c-date").value,
        notes: "",
      }];
      saveExpenses(currentUser, updated);
      renderExpenses("read");
      document.querySelector('[data-exp="read"]').click();
    };
    return;
  }

  if (mode === "update" || mode === "delete") {
    if (!list.length) {
      el.innerHTML = "<p>No expenses.</p>";
      return;
    }
    const opts = list.map((e) => `<option value="${e.id}">#${e.id} ${e.title}</option>`).join("");
    if (mode === "delete") {
      el.innerHTML = `<h3>Delete</h3><select id="d-id">${opts}</select><button class="btn primary" id="d-go">Delete</button>`;
      $("d-go").onclick = () => {
        const id = parseInt($("d-id").value, 10);
        saveExpenses(currentUser, list.filter((e) => e.id !== id));
        renderExpenses("read");
        document.querySelector('[data-exp="read"]').click();
      };
      return;
    }
    el.innerHTML = `<h3>Edit</h3><select id="e-id">${opts}</select>
      <input id="e-title" /><input id="e-amount" type="number" />
      <select id="e-cat">${CATEGORIES.map((c) => `<option>${c}</option>`).join("")}</select>
      <input id="e-date" type="date" /><button class="btn primary" id="e-save">Save</button>`;
    const fill = () => {
      const e = list.find((x) => x.id === parseInt($("e-id").value, 10));
      if (!e) return;
      $("e-title").value = e.title;
      $("e-amount").value = e.amount;
      $("e-cat").value = e.category;
      $("e-date").value = e.expense_date;
    };
    $("e-id").onchange = fill;
    fill();
    $("e-save").onclick = () => {
      const id = parseInt($("e-id").value, 10);
      const updated = list.map((e) =>
        e.id === id
          ? {
              ...e,
              title: $("e-title").value.trim(),
              amount: parseFloat($("e-amount").value),
              category: $("e-cat").value,
              expense_date: $("e-date").value,
            }
          : e
      );
      saveExpenses(currentUser, updated);
      renderExpenses("read");
      document.querySelector('[data-exp="read"]').click();
    };
    return;
  }

  if (mode === "ai") {
    el.innerHTML = `<h3>AI insights (@google/genai SDK)</h3><button class="btn primary" id="ai-run">Analyze expenses</button><div id="ai-out"></div>`;
    $("ai-run").onclick = async () => {
      $("ai-out").textContent = "Running SDK…";
      try {
        const res = await fetch("/api/analyze", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ username: currentUser, expenses: list }),
        });
        const data = await res.json();
        $("ai-out").textContent = data.ok ? data.text : data.error;
      } catch (e) {
        $("ai-out").textContent = e.message;
      }
    };
  }
}

document.querySelectorAll(".tab").forEach((btn) => {
  btn.onclick = () => {
    document.querySelectorAll(".tab").forEach((b) => b.classList.remove("active"));
    btn.classList.add("active");
    $("practice-panel").classList.toggle("hidden", btn.dataset.tab !== "practice");
    $("expenses-panel").classList.toggle("hidden", btn.dataset.tab !== "expenses");
  };
});

document.querySelectorAll(".subtab").forEach((btn) => {
  btn.onclick = () => {
    document.querySelectorAll(".subtab").forEach((b) => b.classList.remove("active"));
    btn.classList.add("active");
    renderExpenses(btn.dataset.exp);
  };
});

$("login-btn").onclick = () => {
  const u = $("login-user").value.trim().toLowerCase();
  const p = $("login-pass").value;
  if (users[u]?.password === p) {
    currentUser = u;
    $("login-error").classList.add("hidden");
    const seed = getExpenses(u);
    if (!seed.length) {
      fetch("/data/expenses.json")
        .then((r) => r.json())
        .then((all) => {
          const demo = all.filter((e) => e.username === u);
          if (demo.length) saveExpenses(u, demo);
          showApp();
        })
        .catch(showApp);
    } else showApp();
  } else {
    $("login-error").textContent = "Invalid username or password";
    $("login-error").classList.remove("hidden");
  }
};

$("logout-btn").onclick = () => {
  currentUser = null;
  showLogin();
};
$("new-q-btn").onclick = pickQuestion;
$("submit-answer").onclick = submitAnswer;

loadData().then(showLogin);
