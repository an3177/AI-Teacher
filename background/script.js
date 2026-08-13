const backgroundCards = document.querySelectorAll('.background-card');
    const continueBtn = document.getElementById('continueBtn');
    let selectedBackground = null;

    backgroundCards.forEach(card => {
      card.addEventListener('click', () => {
        backgroundCards.forEach(c => c.classList.remove('selected'));
        

        card.classList.add('selected');
        

        selectedBackground = card.getAttribute('data-background');
        

        continueBtn.disabled = false;
        

        document.querySelector('.hint').textContent = 'Click continue when ready';
      });
    });

    continueBtn.addEventListener('click', () => {
      if (selectedBackground) {

        localStorage.setItem('selectedBackground', selectedBackground);
        

        window.location.href = '/chatroom/index.html';
      }
    });
