let carList = [];
let currentRow = 0;
const maxGuesses = 7;
let countdownInterval = null;
let correctCarName = null; // Stores correct car name when game ends
let revealedCorrectValues = {}; // Stores revealed correct values for hints
let correctColumns = new Set(); // Track which columns are fully correct
let hintsAvailable = 0;
let hintsUsed = 0;
let gameState = {
    dayNumber: null,
    guesses: [],
    currentRow: 0,
    hintsUsed: 0,
    hintsAvailable: 0,
    correctColumns: [],
    gameOver: false,
    won: false
};

// Load game state from localStorage
function loadGameState(dayNumber) {
    const saved = localStorage.getItem('supercardle_state');
    if (saved) {
        const state = JSON.parse(saved);
        if (state.dayNumber === dayNumber) {
            return state;
        }
    }
    return null;
}

// Save game state to localStorage
function saveGameState() {
    gameState.dayNumber = parseInt(document.getElementById('day-number').textContent.replace('Day #', ''));
    gameState.currentRow = currentRow;
    gameState.hintsUsed = hintsUsed;
    gameState.hintsAvailable = hintsAvailable;
    gameState.correctColumns = Array.from(correctColumns);
    localStorage.setItem('supercardle_state', JSON.stringify(gameState));
}

// Fetch the car list from the server
fetch('cars')
    .then(response => response.json())
    .then(data => {
        carList = data;
    });

// Fetch day info and start countdown
fetch('day-info')
    .then(response => response.json())
    .then(data => {
        document.getElementById('day-number').textContent = `Day #${data.day_number}`;
        startCountdown(data.seconds_until_next);
        
        // Load saved game state if it exists
        const saved = loadGameState(data.day_number);
        if (saved) {
            restoreGameState(saved);
        }
    });

// Restore game state from saved data
async function restoreGameState(saved) {
    currentRow = saved.currentRow;
    hintsUsed = saved.hintsUsed;
    hintsAvailable = saved.hintsAvailable;
    correctColumns = new Set(saved.correctColumns);
    gameState = saved;
    
    // Replay all previous guesses WITHOUT animations
    for (let i = 0; i < saved.guesses.length; i++) {
        await displayCarStats(saved.guesses[i], i, true);
    }
    
    // Show hints if available
    if (hintsAvailable > hintsUsed) {
        showHintMessage();
    }
    
    // If game was over, disable input and show modal
    if (saved.gameOver) {
        input.disabled = true;
        enterBtn.disabled = true;
        if (saved.won) {
            showGameOverModal(true);
        } else {
            showGameOverModal(false);
        }
    }
}

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

async function displayCarStats(carName, rowIndex, skipAnimations = false) {
    // Check the guess with the server
    const response = await fetch('check-guess', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({ car_name: carName })
    });
    const result = await response.json();
    
    if (result.error) return;
    
    const row = gridRows[rowIndex];
    const cells = row.querySelectorAll('.grid-cell');
    
    // Helper function to parse numeric values (remove commas)
    const parseNum = (val) => {
        if (typeof val === 'string') {
            return parseFloat(val.replace(/,/g, ''));
        }
        return parseFloat(val);
    };
    
    // First, collect ALL hint text from ALL previous rows including current
    const revealedHints = [];
    for (let i = 0; i <= rowIndex; i++) {
        const r = gridRows[i];
        const c = r.querySelectorAll('.grid-cell');
        c.forEach((cell, index) => {
            if (cell.classList.contains('hint-text') && index >= 2) {
                // Check if we already have this index
                if (!revealedHints.some(h => h.index === index)) {
                    revealedHints.push({ index: index, value: cell.textContent });
                }
            }
        });
    }
    
    if (skipAnimations) {
        // No animations - set everything immediately
        cells[0].textContent = rowIndex + 1;
        // Split car name into make and model
        const parts = carName.split(' ');
        const make = result.make;
        const model = parts.slice(1).join(' ');
        cells[1].innerHTML = `${make}<br><span class="model-text">(${model})</span>`;
    } else {
        // Then fade out all cells in the row and remove hint text/emojis
        cells.forEach(cell => {
            cell.classList.remove('hint-text', 'hint-available');
            cell.style.cursor = 'default';
            delete cell.dataset.hintCol;
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
        const parts = carName.split(' ');
        const make = result.make;
        const model = parts.slice(1).join(' ');
        cells[1].innerHTML = `${make}<br><span class="model-text">(${model})</span>`;
        cells[1].classList.remove('fade-out');
        cells[1].classList.add('fade-in');
        
        // Wait a bit before starting the stats
        await new Promise(resolve => setTimeout(resolve, 300));
    }
    
    const stats = [
        { value: result.comparisons.year.value, status: result.comparisons.year.status, type: 'number' },
        { value: result.comparisons.engine_size.value, status: result.comparisons.engine_size.status, type: 'engine' },
        { value: result.comparisons.horsepower.value, status: result.comparisons.horsepower.status, type: 'number' },
        { value: result.comparisons.torque.value, status: result.comparisons.torque.status, type: 'number' },
        { value: result.comparisons.price.value, status: result.comparisons.price.status, type: 'number' },
        { value: result.comparisons.country.value, status: result.comparisons.country.status, type: 'string' }
    ];
    
    if (skipAnimations) {
        // No animations - set stats immediately
        stats.forEach((stat, index) => {
            const cell = cells[index + 2];
            cell.textContent = stat.value;
        });
    } else {
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
    }
    
    // Now apply all colors at once
    // Car make color
    if (result.make_correct) {
        cells[1].classList.add('correct');
    } else {
        cells[1].classList.add('incorrect');
    }
    
    // Apply colors to all stat cells
    stats.forEach((stat, index) => {
        const cell = cells[index + 2];
        let isCorrect = false;
        
        if (stat.type === 'engine') {
            const guessIsElectric = stat.value.toString().toLowerCase() === 'electric';
            
            if (stat.status === 'correct') {
                cell.classList.add('correct');
                isCorrect = true;
            } else if (stat.status === 'incorrect') {
                // For incorrect, show strikethrough if electric/gas mismatch
                if (guessIsElectric) {
                    cell.innerHTML = `<span style="text-decoration: line-through;">${stat.value}</span>`;
                }
                cell.classList.add('incorrect');
            } else if (stat.status === 'lower') {
                cell.classList.add('too-low');
                cell.innerHTML = `${stat.value}<span class="arrow">↑</span>`;
            } else if (stat.status === 'higher') {
                cell.classList.add('too-high');
                cell.innerHTML = `${stat.value}<span class="arrow">↓</span>`;
            }
        } else if (stat.type === 'number') {
            if (stat.status === 'correct') {
                cell.classList.add('correct');
                isCorrect = true;
            } else if (stat.status === 'lower') {
                cell.classList.add('too-low');
                cell.innerHTML = `${stat.value}<span class="arrow">↑</span>`;
            } else if (stat.status === 'higher') {
                cell.classList.add('too-high');
                cell.innerHTML = `${stat.value}<span class="arrow">↓</span>`;
            }
        } else {
            // Country comparison (string)
            if (stat.status === 'correct') {
                cell.classList.add('correct');
                isCorrect = true;
            } else {
                cell.classList.add('incorrect');
            }
        }
        
        // Track correct columns
        if (isCorrect) {
            const colNames = ['year', 'engine', 'hp', 'torque', 'price', 'country'];
            correctColumns.add(colNames[index]);
        }
    });
    
    // Apply hint text to all subsequent rows
    for (let i = rowIndex + 1; i < maxGuesses; i++) {
        const row = gridRows[i];
        const cells = row.querySelectorAll('.grid-cell');
        revealedHints.forEach(hint => {
            const cell = cells[hint.index];
            if (!cell.textContent || cell.classList.contains('hint-available')) {
                cell.textContent = hint.value;
                cell.classList.remove('hint-available');
                cell.classList.add('hint-text');
                cell.style.cursor = 'default';
            }
        });
    }
    
    // If there are hints available and we're not at the last guess, add hint emojis to next row
    if (hintsAvailable > hintsUsed && rowIndex + 1 < maxGuesses) {
        const nextRow = gridRows[rowIndex + 1];
        const nextCells = nextRow.querySelectorAll('.grid-cell');
        
        const colMap = [
            { index: 2, col: 'year' },
            { index: 3, col: 'engine' },
            { index: 4, col: 'hp' },
            { index: 5, col: 'torque' },
            { index: 6, col: 'price' },
            { index: 7, col: 'country' }
        ];
        
        colMap.forEach(({ index, col }) => {
            if (!correctColumns.has(col)) {
                const cell = nextCells[index];
                if (!cell.classList.contains('hint-text')) {
                    cell.textContent = '💡';
                    cell.classList.add('hint-available');
                    cell.dataset.hintCol = col;
                    cell.style.cursor = 'pointer';
                }
            }
        });
    }
    
    // Return whether the guess was correct
    return result.is_correct;
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
        
        // Save the guess to game state
        gameState.guesses.push(guessedCar);
        
        const isCorrect = await displayCarStats(guessedCar, currentRow);
        
        // If correct, store the car name for later display
        if (isCorrect) {
            correctCarName = guessedCar;
        }
        
        currentRow++;
        
        input.value = '';
        suggestionsDiv.classList.remove('active');
        
        // Check for hints after guess 2 and 5
        if (currentRow === 2 && correctColumns.size === 0) {
            hintsAvailable++;
            showHintMessage();
        } else if (currentRow === 5 && correctColumns.size < 2) {
            hintsAvailable++;
            showHintMessage();
        }
        
        if (isCorrect) {
            // Won the game - keep disabled
            gameState.gameOver = true;
            gameState.won = true;
            saveGameState();
            setTimeout(() => showGameOverModal(true), 1000);
        } else if (currentRow >= maxGuesses) {
            // Lost the game - keep disabled
            gameState.gameOver = true;
            gameState.won = false;
            saveGameState();
            setTimeout(() => showGameOverModal(false), 1000);
        } else {
            // Save state after each guess
            saveGameState();
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

function showHintMessage() {
    // Add emojis to the next row cells for columns that can be revealed
    if (currentRow < maxGuesses) {
        const nextRow = gridRows[currentRow];
        const cells = nextRow.querySelectorAll('.grid-cell');
        
        // Column indices for data columns (skip # and Car Make)
        const colMap = [
            { index: 2, col: 'year' },
            { index: 3, col: 'engine' },
            { index: 4, col: 'hp' },
            { index: 5, col: 'torque' },
            { index: 6, col: 'price' },
            { index: 7, col: 'country' }
        ];
        
        colMap.forEach(({ index, col }) => {
            if (!correctColumns.has(col)) {
                const cell = cells[index];
                if (!cell.classList.contains('hint-revealed')) {
                    cell.textContent = '💡';
                    cell.classList.add('hint-available');
                    cell.dataset.hintCol = col;
                    cell.style.cursor = 'pointer';
                }
            }
        });
    }
}

async function revealColumn(columnName) {
    if (hintsUsed >= hintsAvailable) return;
    
    // Fetch the correct value for this column from server
    const response = await fetch('reveal-hint', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({ column_name: columnName })
    });
    const result = await response.json();
    
    if (result.error) return;
    
    hintsUsed++;
    correctColumns.add(columnName);
    revealedCorrectValues[columnName] = result.value;
    
    const value = result.value;
    
    // Add faint text to this column for current row and ALL subsequent rows
    const colIndexMap = {
        'year': 2,
        'engine': 3,
        'hp': 4,
        'torque': 5,
        'price': 6,
        'country': 7
    };
    const colIndex = colIndexMap[columnName];
    
    // Apply hint text to current row and all subsequent rows
    for (let i = currentRow; i < maxGuesses; i++) {
        const row = gridRows[i];
        const cell = row.querySelectorAll('.grid-cell')[colIndex];
        cell.textContent = value;
        cell.classList.remove('hint-available');
        cell.classList.add('hint-text');
        cell.style.cursor = 'default';
        delete cell.dataset.hintCol;
    }
    
    // Hide hint message if all hints used
    if (hintsUsed >= hintsAvailable) {
        // Remove remaining emoji indicators from cells
        if (currentRow < maxGuesses) {
            const nextRow = gridRows[currentRow];
            const cells = nextRow.querySelectorAll('.grid-cell.hint-available');
            cells.forEach(cell => {
                cell.textContent = '';
                cell.classList.remove('hint-available');
                cell.style.cursor = 'default';
                delete cell.dataset.hintCol;
            });
        }
    }
    
    // Save state after revealing hint
    saveGameState();
}

// Add click handlers to cells with hints
document.addEventListener('click', (e) => {
    if (e.target.classList.contains('hint-available')) {
        const col = e.target.dataset.hintCol;
        if (col) {
            revealColumn(col);
        }
    }
});

function showGameOverModal(won) {
    const modal = document.getElementById('game-over-modal');
    const modalTitle = document.getElementById('modal-title');
    const carNameDisplay = document.getElementById('car-name-display');
    const fullCarImage = document.getElementById('full-car-image');
    
    // Load the full image only when modal is shown
    if (!fullCarImage.src) {
        fullCarImage.src = 'full-image.png';
    }
    
    if (won) {
        modalTitle.textContent = 'You won! 🎉';
    } else {
        modalTitle.textContent = 'Game Over!';
    }
    
    // Fetch the correct answer from server if not already known
    if (!correctCarName) {
        fetch('reveal-answer', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            }
        })
        .then(response => response.json())
        .then(data => {
            correctCarName = data.name;
            carNameDisplay.textContent = correctCarName;
        });
    } else {
        carNameDisplay.textContent = correctCarName;
    }
    
    modal.classList.add('show');
}

// Close modal functionality
document.getElementById('close-modal').addEventListener('click', function() {
    const modal = document.getElementById('game-over-modal');
    modal.classList.remove('show');
});
