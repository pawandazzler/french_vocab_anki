// -------------------- Helpers --------------------
function getColorCircle(color) {
    if (color === 'red') return 'bg-red-500';
    if (color === 'amber') return 'bg-yellow-400';
    if (color === 'green') return 'bg-green-500';
    return 'bg-gray-300';
  }
  
  async function updateColorCounts() {
    const res = await fetch('/api/get_color_counts');
    const counts = await res.json();
    document.getElementById('count-green').textContent = counts.green;
    document.getElementById('count-amber').textContent = counts.amber;
    document.getElementById('count-red').textContent = counts.red;
    document.getElementById('count-gray').textContent = counts.gray;
  }

  // -------------------- Load Vocab --------------------
  async function loadVocab() {
    const filter = document.getElementById('color-filter').value;
    let url = '/api/get_random_words';
    if (filter !== 'all') url += `?color=${encodeURIComponent(filter)}`;
  
    const res = await fetch(url);
    const data = await res.json();
    renderVocab(data);
  
    // update color counts
    updateColorCounts();
  }
  
  // -------------------- Render Cards --------------------
  function renderVocab(words) {
    const container = document.getElementById('vocab-container');
    container.innerHTML = '';
  
    words.forEach(w => {
      const card = document.createElement('div');
      card.className = `p-3 rounded-xl shadow bg-white border-2 border-transparent transition-all flex flex-col gap-2`;
      card.dataset.english = w.english;
      card.dataset.color = w.color;
  
      card.innerHTML = `
        <!-- Row 1: English + status + manual colors + audio -->
        <div class="flex justify-between items-center w-full">
          <div class="flex items-center gap-3">
            <h2 class="text-lg font-semibold text-gray-800">${w.english}</h2>
            <span class="inline-block w-3 h-3 rounded-full ${getColorCircle(w.color)}"></span>
            <div class="flex items-center gap-1">
              <button class="color-btn bg-red-500 w-5 h-5 rounded-full" data-color="red"></button>
              <button class="color-btn bg-yellow-400 w-5 h-5 rounded-full" data-color="amber"></button>
              <button class="color-btn bg-green-500 w-5 h-5 rounded-full" data-color="green"></button>
            </div>
          </div>
          <button class="bg-gray-400 hover:bg-gray-500 text-white px-3 py-1 rounded audio-btn">🔊</button>
        </div>
  
        <!-- Row 2: Input + Check -->
        <div class="flex items-center gap-2">
          <input type="text" placeholder="Enter French" class="border p-2 rounded flex-grow french-input focus:ring-2 focus:ring-blue-300 outline-none">
          <button class="bg-blue-500 hover:bg-blue-600 text-white px-3 py-2 rounded validate-btn">Check</button>
        </div>
  
        <p class="text-sm result text-center mt-1"></p>
      `;
  
      container.appendChild(card);
    });
  
    addEventListeners();
  }
  
  // -------------------- Event Listeners --------------------
  function addEventListeners() {
    // Validate
    document.querySelectorAll('.validate-btn').forEach(btn => {
      const inputElem = btn.closest('div[data-english]').querySelector('.french-input');
  
      // Disable check if empty
      btn.disabled = !inputElem.value.trim();
      btn.classList.toggle('opacity-50', !inputElem.value.trim());
  
      inputElem.addEventListener('input', () => {
        const hasText = inputElem.value.trim().length > 0;
        btn.disabled = !hasText;
        btn.classList.toggle('opacity-50', !hasText);
      });
  
      btn.addEventListener('click', async (e) => {
        const card = e.target.closest('div[data-english]');
        const input = inputElem.value.trim();
        const result = card.querySelector('.result');

        if (!input) {
            result.textContent = "⚠️ Please enter a French word";
            result.className = "text-sm result text-yellow-600";
            return;
        }

        const english = card.dataset.english;
        const res = await fetch('/api/check_answer', {
            method: 'POST',
            headers: {'Content-Type':'application/json'},
            body: JSON.stringify({english, french: input})
        });

        const data = await res.json();
        if (data.correct) {
            result.textContent = "✅ Correct!";
            result.className = "text-sm result text-green-600";
            card.style.borderColor = "#22c55e";
            await updateColor(card, 'green');  // update backend + UI
        } else {
            result.textContent = `❌ Incorrect (correct: ${data.correct_answer})`;
            result.className = "text-sm result text-red-600";
            card.style.borderColor = "#ef4444";
            await updateColor(card, 'red');
        }

        // --- Update color counts here ---
        updateColorCounts();
        });
    });
  
    // Audio
    document.querySelectorAll('.audio-btn').forEach(btn => {
      btn.addEventListener('click', async (e) => {
        const card = e.target.closest('div[data-english]');
        const english = card.dataset.english;
        const res = await fetch(`/api/play_audio?english=${encodeURIComponent(english)}`);
        if (res.ok) {
          const blob = await res.blob();
          const url = URL.createObjectURL(blob);
          const audio = new Audio(url);
          audio.play();
        }
      });
    });
  
    // Manual color buttons
    document.querySelectorAll('.color-btn').forEach(btn => {
        btn.addEventListener('click', async (e) => {
          const card = e.target.closest('div[data-english]');
          const color = e.target.dataset.color;
          await updateColor(card, color);
      
          // --- Update color counts after manual change ---
          updateColorCounts();
        });
      });
  }
  
  // Update color backend + UI
  async function updateColor(card, color) {
    const english = card.dataset.english;
    await fetch('/api/update_color', {
      method: 'POST',
      headers: {'Content-Type':'application/json'},
      body: JSON.stringify({english, color})
    });
    card.dataset.color = color;
    const dot = card.querySelector('span.inline-block');
    dot.className = `inline-block w-3 h-3 rounded-full ${getColorCircle(color)}`;
  }
  
  // -------------------- Refresh button --------------------
  document.getElementById('refresh-btn').addEventListener('click', loadVocab);
  
  // -------------------- Login --------------------
  document.getElementById('login-btn').addEventListener('click', async () => {
    const username = document.getElementById('username-input').value.trim();
    if (!username) return alert("Enter a username");
  
    const res = await fetch('/login', {
      method: 'POST',
      body: new URLSearchParams({username})
    });
  
    if (res.ok) {
      document.getElementById('login-modal').style.display = 'none';
      loadVocab();
    } else {
      alert("Login failed");
    }
  });
  