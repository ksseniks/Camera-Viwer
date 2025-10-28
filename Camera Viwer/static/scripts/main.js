document.addEventListener('DOMContentLoaded', () => {
  const container = document.getElementById('container');
  if (!container) throw new Error('Контейнер не найден');

  let fullscreenIndex = null;
  let roiEditMode = false;

  const rows = container.dataset.rows;
  const cols = container.dataset.cols;

  container.style.gridTemplateRows = `repeat(${rows}, 1fr)`;
  container.style.gridTemplateColumns = `repeat(${cols}, 1fr)`;

  container.addEventListener('click', function(event) {
    const camDiv = event.target.closest('.camera');
    if (!camDiv) return;

    const index = camDiv.getAttribute('data-index');
    if (index === null) return;

    if (roiEditMode) return; // блокируем смену камеры, если в режиме редактирования

    if (fullscreenIndex === index) {
      // Выход из fullscreen
      fullscreenIndex = null;
      container.classList.remove('fullscreen');

      container.style.gridTemplateRows = `repeat(${rows}, 1fr)`;
      container.style.gridTemplateColumns = `repeat(${cols}, 1fr)`;

      [...container.children].forEach(div => {
        div.style.display = 'block';
        div.style.width = '';
        div.style.height = '';
        div.classList.remove('fullscreen');
      });

      removeROIButton();
      removeROICanvas();

    } else {
      // Вход в fullscreen
      fullscreenIndex = index;
      container.classList.add('fullscreen');

      container.style.gridTemplateRows = 'none';
      container.style.gridTemplateColumns = 'none';

      [...container.children].forEach((div, i) => {
        if (i == index) {
          div.style.display = 'flex';
          div.style.flexDirection = 'column';
          div.style.alignItems = 'center';
          div.style.width = '100vw';
          div.style.height = '100vh';
          div.classList.add('fullscreen');
        } else {
          div.style.display = 'none';
          div.classList.remove('fullscreen');
        }
      });

      // Передаём имя камеры вместо индекса
      const camName = camDiv.getAttribute('data-name');
      addROIButton(camName);
    }
  });

  // camName теперь строка — имя камеры
  function addROIButton(camName) {
    const camDiv = container.querySelector(`.camera[data-name="${camName}"]`);
    if (!camDiv) return;

    if (camDiv.querySelector('.edit-roi-btn')) return;

    const h2 = camDiv.querySelector('h2');
    if (!h2) return;

    const btn = document.createElement('button');
    btn.textContent = 'Изменить кадр';
    btn.classList.add('edit-roi-btn');

    btn.addEventListener('click', () => {
      roiEditMode = true;
      startROIEdit(camName, btn);
    });

    h2.appendChild(btn);
  }

  function removeROIButton() {
    const btn = container.querySelector('.edit-roi-btn');
    if (btn) btn.remove();
    roiEditMode = false;
  }

  function removeROICanvas() {
    const canvas = container.querySelector('canvas.roi-canvas');
    if (canvas) {
      canvas.removeEventListener('mousemove', mouseMoveHandler);
      canvas.removeEventListener('click', mouseClickHandler);
      canvas.remove();
    }
  }

  let mouseMoveHandler, mouseClickHandler;

  // camName — строка с именем камеры
  function startROIEdit(camName, btn) {
    const camDiv = container.querySelector(`.camera[data-name="${camName}"]`);
    if (!camDiv) return;

    const img = camDiv.querySelector('img');
    if (!img) return;

    let canvas = camDiv.querySelector('canvas.roi-canvas');
    if (!canvas) {
      canvas = document.createElement('canvas');
      canvas.classList.add('roi-canvas');
      canvas.style.position = 'absolute';
      canvas.style.top = img.offsetTop + 'px';
      canvas.style.left = img.offsetLeft + 'px';
      canvas.style.pointerEvents = 'auto';
      canvas.style.zIndex = '10';

      camDiv.style.position = 'relative';
      camDiv.appendChild(canvas);
    }

    canvas.width = img.clientWidth;
    canvas.height = img.clientHeight;
    canvas.style.width = img.clientWidth + 'px';
    canvas.style.height = img.clientHeight + 'px';

    const ctx = canvas.getContext('2d');

    let startPoint = null;
    let isDrawing = false;

    function drawRect(x, y) {
      ctx.clearRect(0, 0, canvas.width, canvas.height);

      const rx = Math.min(startPoint.x, x);
      const ry = Math.min(startPoint.y, y);
      const rw = Math.abs(startPoint.x - x);
      const rh = Math.abs(startPoint.y - y);

      ctx.strokeStyle = 'red';
      ctx.lineWidth = 2;
      ctx.strokeRect(rx, ry, rw, rh);
    }

    canvas.addEventListener('mousedown', (e) => {
      const rect = canvas.getBoundingClientRect();
      startPoint = {
        x: e.clientX - rect.left,
        y: e.clientY - rect.top
      };
      isDrawing = true;
    });

    canvas.addEventListener('mousemove', (e) => {
      if (!isDrawing) return;
      const rect = canvas.getBoundingClientRect();
      const currentX = e.clientX - rect.left;
      const currentY = e.clientY - rect.top;
      drawRect(currentX, currentY);
    });

    canvas.addEventListener('mouseup', (e) => {
      if (!isDrawing) return;
      isDrawing = false;

      const rect = canvas.getBoundingClientRect();
      const endX = e.clientX - rect.left;
      const endY = e.clientY - rect.top;

      const rx = Math.min(startPoint.x, endX);
      const ry = Math.min(startPoint.y, endY);
      const rw = Math.abs(startPoint.x - endX);
      const rh = Math.abs(startPoint.y - endY);

      ctx.clearRect(0, 0, canvas.width, canvas.height);

      fetch(`/setroi/${encodeURIComponent(camName)}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          x: Math.round(rx),
          y: Math.round(ry),
          width: Math.round(rw),
          height: Math.round(rh)
        })
      })
      .then(async response => {
        if (!response.ok) {
          const text = await response.text();
          console.error('Ошибка сервера:', response.status, text);
          throw new Error(`Ошибка при отправке ROI: ${response.status} ${text}`);
        }
        return response.json();
      })
      .then(data => {
        console.log('Ответ сервера:', data);
        alert(`ROI для камеры "${camName}" установлен и сохранён на сервере.`);
      })
      .catch(err => {
        alert(`Ошибка при сохранении ROI: ${err.message}`);
      });

      roiEditMode = false;
      startPoint = null;

      btn.disabled = false;

      canvas.remove();
    });

    btn.disabled = true;
  }
});
