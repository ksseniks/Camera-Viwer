document.addEventListener('DOMContentLoaded', () => {
    const hotbar = document.getElementById('hotbar');
    const buttons = document.querySelectorAll('.hotbar-button');

    document.addEventListener('mousemove', (e) => {
        if (e.clientX <= 20) {
            hotbar.classList.add('show');
        } else if (e.clientX > 80) {
            hotbar.classList.remove('show');
        }
    });

    buttons.forEach(btn => {
        btn.addEventListener('click', () => {
            alert(`Нажата кнопка: ${btn.textContent}`);
        });
    });
});
