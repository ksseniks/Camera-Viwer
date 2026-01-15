document.addEventListener('DOMContentLoaded', () => {
  const container = document.getElementById('container');
  if (!container) throw new Error('Контейнер не найден');

  let fullscreenIndex = null;

  container.addEventListener('click', (event) => {
    const camDiv = event.target.closest('.camera');
    if (!camDiv) return;

    const index = camDiv.dataset.index;
    if (index === undefined) return;

    if (fullscreenIndex === index) exitFullscreen();
    else enterFullscreen(camDiv, index);
  });

  function enterFullscreen(camDiv, index) {
    fullscreenIndex = index;
    document.body.classList.add('fullscreen');

    if (camDiv.requestFullscreen) camDiv.requestFullscreen();
    else if (camDiv.webkitRequestFullscreen) camDiv.webkitRequestFullscreen();
    else if (camDiv.msRequestFullscreen) camDiv.msRequestFullscreen();

    [...container.children].forEach((div, i) => {
      div.style.display = (i == index) ? 'block' : 'none';
    });
  }

  function exitFullscreen() {
    fullscreenIndex = null;
    document.body.classList.remove('fullscreen');
    if (document.exitFullscreen) document.exitFullscreen();

    [...container.children].forEach(div => div.style.display = 'block');
  }

});
