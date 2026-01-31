const backgroundCards = document.querySelectorAll('.background-card');
    const continueBtn = document.getElementById('continueBtn');
    let selectedBackground = null;

    backgroundCards.forEach(card => {
      card.addEventListener('click', () => {
        // Remove selected class from all cards
        backgroundCards.forEach(c => c.classList.remove('selected'));
        
        // Add selected class to clicked card
        card.classList.add('selected');
        
        // Get the background type
        selectedBackground = card.getAttribute('data-background');
        
        // Enable continue button
        continueBtn.disabled = false;
        
        // Update hint text
        document.querySelector('.hint').textContent = 'Click continue when ready';
      });
    });

    continueBtn.addEventListener('click', () => {
      if (selectedBackground) {
        // Store the selected background in localStorage
        localStorage.setItem('selectedBackground', selectedBackground);
        
        // Redirect to the chat page
        window.location.href = '/chatroom/index.html';
      }
    });