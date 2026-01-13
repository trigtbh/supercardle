let carList = [];
let currentRow = 0;
const maxGuesses = 7;
let correctCar = null;
let countdownInterval = null;

// Fetch the car list from the server
fetch('/cars')
    .then(response => response.json())
    .then(data => {
        carList = data;
    });

// Fetch the correct car data
fetch('/correct-car')
    .then(response => response.json())
    .then(data => {
        correctCar = data;
    });

// Fetch day info and start countdown
fetch('/day-info')
    .then(response => response.json())
    .then(data => {
        document.getElementById('day-number').textContent = `Day #${data.day_number}`;
        startCountdown(data.seconds_until_next);
    });

function formatTime(seconds) {
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    const secs = seconds % 60;
    return `${String(hours).padStart(2, '0')}:${String(minutes).padStart(2, '0')}:${String(secs).padStart(2, '0')}`;
}

function startCountdown(initialSeconds) {
    let secondsLeft = initialSeconds;
    const timerElement = document.getElementById('countdown-timer');
    
    function updateTimer() {
        if (secondsLeft <= 0) {
            clearInterval(countdownInterval);
            timerElement.textContent = 'Refresh!';
            timerElement.classList.add('expired');
            timerElement.style.cursor = 'pointer';
            timerElement.onclick = () => location.reload();
        } else {
            timerElement.textContent = formatTime(secondsLeft);
            secondsLeft--;
        }
    }
    
    updateTimer();
    countdownInterval = setInterval(updateTimer, 1000);
}

const input = document.getElementById('car-input');
const suggestionsDiv = document.getElementById('suggestions');
const enterBtn = document.getElementById('enter-btn');
const gridRows = document.querySelectorAll('.grid-row');

function isValidCar(value) {
    return carList.some(car => car.toLowerCase() === value.toLowerCase());
}

async function displayCarStats(carName, rowIndex) {
    // Fetch car details
    const response = await fetch(`/car/${encodeURIComponent(carName)}`);
    const carData = await response.json();
    
    if (!carData) return;
    
    const row = gridRows[rowIndex];
    const cells = row.querySelectorAll('.grid-cell');
    
    // Helper function to parse numeric values (remove commas)
    const parseNum = (val) => {
        if (typeof val === 'string') {
            return parseFloat(val.replace(/,/g, ''));
        }
        return parseFloat(val);
    };
    
    // First, fade out all cells in the row
    cells.forEach(cell => {
        cell.classList.add('fade-out');
    });
    
    // Wait for fade-out to complete
    await new Promise(resolve => setTimeout(resolve, 300));
    
    // Set and fade in guess number first
    cells[0].textContent = rowIndex + 1;
    cells[0].classList.remove('fade-out');
    cells[0].classList.add('fade-in');
    
    // Wait for guess number to finish fading in
    await new Promise(resolve => setTimeout(resolve, 400));
    
    // Then set and fade in car name
    const nameParts = carName.split(' ');
    const make = nameParts[0];
    const model = nameParts.slice(1).join(' ');
    cells[1].innerHTML = `${make}<br><span class="model-text">(${model})</span>`;
    cells[1].classList.remove('fade-out');
    cells[1].classList.add('fade-in');
    
    // Wait a bit before starting the stats
    await new Promise(resolve => setTimeout(resolve, 300));
    
    const stats = [
        { value: carData.year, correct: correctCar.year, type: 'number' },
        { value: carData.engine_size, correct: correctCar.engine_size, type: 'engine' },
        { value: carData.horsepower, correct: correctCar.horsepower, type: 'number' },
        { value: carData.torque, correct: correctCar.torque, type: 'number' },
        { value: carData.price, correct: correctCar.price, type: 'number' },
        { value: carData.country, correct: correctCar.country, type: 'string' }
    ];
    
    // Fade in each stat cell with delays
    stats.forEach((stat, index) => {
        setTimeout(() => {
            const cell = cells[index + 2];
            cell.textContent = stat.value;
            cell.classList.remove('fade-out');
            cell.classList.add('fade-in');
        }, index * 300);
    });
    
    // Wait for all cells to fade in
    await new Promise(resolve => setTimeout(resolve, (stats.length * 300) + 300));
    
    // Now apply all colors at once
    // Car make color
    if (make.toLowerCase() === correctCar.make.toLowerCase()) {
        cells[1].classList.add('correct');
    } else {
        cells[1].classList.add('incorrect');
    }
    
    // Apply colors to all stat cells
    stats.forEach((stat, index) => {
        const cell = cells[index + 2];
        
        if (stat.type === 'engine') {
            const guessIsElectric = stat.value.toString().toLowerCase() === 'electric';
            const correctIsElectric = stat.correct.toString().toLowerCase() === 'electric';
            
            // Check if electric/gas mismatch (one is electric, other is gas)
            if (guessIsElectric !== correctIsElectric) {
                // Mismatch: mark as incorrect with strikethrough
                cell.classList.add('incorrect');
                cell.innerHTML = `<span style="text-decoration: line-through;">${stat.value}</span>`;
            } else if (guessIsElectric && correctIsElectric) {
                // Both are electric: correct match
                cell.classList.add('correct');
            } else {
                // Both are gas (numeric), compare values
                const guessVal = parseNum(stat.value);
                const correctVal = parseNum(stat.correct);
                
                if (guessVal === correctVal) {
                    cell.classList.add('correct');
                } else if (guessVal < correctVal) {
                    cell.classList.add('too-low');
                    cell.innerHTML = `${stat.value}<span class="arrow">↑</span>`;
                } else {
                    cell.classList.add('too-high');
                    cell.innerHTML = `${stat.value}<span class="arrow">↓</span>`;
                }
            }
        } else if (stat.type === 'number') {
            const guessVal = parseNum(stat.value);
            const correctVal = parseNum(stat.correct);
            
            if (guessVal === correctVal) {
                cell.classList.add('correct');
            } else if (guessVal < correctVal) {
                cell.classList.add('too-low');
                cell.innerHTML = `${stat.value}<span class="arrow">↑</span>`;
            } else {
                cell.classList.add('too-high');
                cell.innerHTML = `${stat.value}<span class="arrow">↓</span>`;
            }
        } else {
            // Country comparison (string)
            if (stat.value.toLowerCase() === stat.correct.toLowerCase()) {
                cell.classList.add('correct');
            } else {
                cell.classList.add('incorrect');
            }
        }
    });
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
enterBtn.addEventListener('click', async function() {
    if (isValidCar(input.value) && currentRow < maxGuesses && !enterBtn.disabled) {
        // Disable button immediately to prevent double-clicks
        enterBtn.disabled = true;
        input.disabled = true;
        
        const guessedCar = input.value;
        await displayCarStats(guessedCar, currentRow);
        currentRow++;
        
        // Check if the guess was correct
        const isCorrect = guessedCar.toLowerCase() === correctCar.name.toLowerCase();
        
        input.value = '';
        suggestionsDiv.classList.remove('active');
        
        if (isCorrect) {
            // Won the game - keep disabled
            setTimeout(() => showGameOverModal(true), 1000);
        } else if (currentRow >= maxGuesses) {
            // Lost the game - keep disabled
            setTimeout(() => showGameOverModal(false), 1000);
        } else {
            // Re-enable input for next guess
            input.disabled = false;
            // Button stays disabled until valid input
        }
    }
});

// Allow enter key to submit
input.addEventListener('keypress', function(e) {
    if (e.key === 'Enter' && !enterBtn.disabled) {
        enterBtn.click();
    }
});

function showGameOverModal(won) {
    const modal = document.getElementById('game-over-modal');
    const modalTitle = document.getElementById('modal-title');
    const carNameDisplay = document.getElementById('car-name-display');
    
    if (won) {
        modalTitle.textContent = 'You won! 🎉';
    } else {
        modalTitle.textContent = 'Game Over!';
    }
    
    carNameDisplay.textContent = correctCar.name;
    modal.classList.add('show');
}

// Close modal functionality
document.getElementById('close-modal').addEventListener('click', function() {
    const modal = document.getElementById('game-over-modal');
    modal.classList.remove('show');
});
