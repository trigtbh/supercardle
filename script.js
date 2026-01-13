let carList = [];

// Fetch the car list from the server
fetch('/cars')
    .then(response => response.json())
    .then(data => {
        carList = data;
    });

const input = document.getElementById('car-input');
const suggestionsDiv = document.getElementById('suggestions');
const enterBtn = document.getElementById('enter-btn');

function isValidCar(value) {
    return carList.some(car => car.toLowerCase() === value.toLowerCase());
}

input.addEventListener('input', function() {
    const value = this.value.toLowerCase();
    suggestionsDiv.innerHTML = '';
    
    // Update button state
    enterBtn.disabled = !isValidCar(value);
    
    if (value.length === 0) {
        suggestionsDiv.classList.remove('active');
        return;
    }
    
    const filtered = carList.filter(car => 
        car.toLowerCase().includes(value)
    ).slice(0, 10);
    
    if (filtered.length > 0) {
        suggestionsDiv.classList.add('active');
        filtered.forEach(car => {
            const div = document.createElement('div');
            div.className = 'suggestion-item';
            div.textContent = car;
            div.addEventListener('click', function() {
                input.value = car;
                suggestionsDiv.classList.remove('active');
                enterBtn.disabled = false;
            });
            suggestionsDiv.appendChild(div);
        });
    } else {
        suggestionsDiv.classList.remove('active');
    }
});

// Close suggestions when clicking outside
document.addEventListener('click', function(e) {
    if (!input.contains(e.target) && !suggestionsDiv.contains(e.target)) {
        suggestionsDiv.classList.remove('active');
    }
});

// Handle enter button click
enterBtn.addEventListener('click', function() {
    if (isValidCar(input.value)) {
        console.log('Valid car entered:', input.value);
        // TODO: Add guess to grid
    }
});

// Allow enter key to submit
input.addEventListener('keypress', function(e) {
    if (e.key === 'Enter' && !enterBtn.disabled) {
        enterBtn.click();
    }
});
