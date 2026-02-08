let carList = [];
let currentRow = 0;
const maxGuesses = 7;
let countdownInterval = null;
let correctCarName = null; // Stores correct car name when game ends
let revealedCorrectValues = {}; // Stores revealed correct values for hints
let correctColumns = new Set(); // Track which columns are fully correct
let hintsAvailable = 0;
let hintsUsed = 0;
let isHistoryMode = false; // Track if we're playing a historical day
let historyDayNumber = null; // The day number when in history mode
let actualCurrentDay = null; // The actual current day (always tracks real day, not historical)
let historyPage = 0; // Current page in history modal (0-indexed)
const DAYS_PER_PAGE = 10; // Number of days to show per page
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

// --- Stats storage and computation (localStorage key: 'supercardle_stats') ---
function loadStats() {
    const raw = localStorage.getItem('supercardle_stats');
    if (!raw) return [];
    try {
        return JSON.parse(raw);
    } catch (e) {
        return [];
    }
}

function saveStatsArray(arr) {
    localStorage.setItem('supercardle_stats', JSON.stringify(arr));
}

function saveStatsEntry(entry) {
    // entry: { dayNumber, won: bool, guesses: number, make: string | null }
    const arr = loadStats();
    const idx = arr.findIndex(e => e.dayNumber === entry.dayNumber);
    if (idx !== -1) {
        arr[idx] = entry; // replace
    } else {
        arr.push(entry);
    }
    saveStatsArray(arr);
}

function computeStats() {
    const arr = loadStats();
    // Average guesses to win (only won games)
    const wins = arr.filter(e => e.won && typeof e.guesses === 'number');
    const avgGuesses = wins.length ? (wins.reduce((s, x) => s + x.guesses, 0) / wins.length) : null;

    // Brand with best average guess number (among wins grouped by make)
    const byBrand = {};
    wins.forEach(w => {
        if (!w.make) return;
        if (!byBrand[w.make]) byBrand[w.make] = { sum: 0, count: 0 };
        byBrand[w.make].sum += w.guesses;
        byBrand[w.make].count += 1;
    });
    let bestBrand = null;
    let bestAvg = null;
    Object.keys(byBrand).forEach(brand => {
        const obj = byBrand[brand];
        const avg = obj.sum / obj.count;
        if (bestAvg === null || avg < bestAvg) {
            bestAvg = avg;
            bestBrand = brand;
        }
    });

    // Win streak: count consecutive winning days from latest recorded day
    // Streak breaks if: 1) a day is lost, 2) there's a gap of more than 1 day
    let streak = 0;
    if (arr.length) {
        // Sort by day number descending
        const sorted = arr.slice().sort((a, b) => b.dayNumber - a.dayNumber);
        const latest = sorted[0].dayNumber;
        
        let expectedDay = latest;
        for (let i = 0; i < sorted.length; i++) {
            const entry = sorted[i];
            
            // Check if this is the expected day
            if (entry.dayNumber !== expectedDay) {
                // Gap detected - streak ends
                break;
            }
            
            // Check if won
            if (!entry.won) {
                // Loss detected - streak ends
                break;
            }
            
            // This day contributes to streak
            streak += 1;
            expectedDay -= 1;
        }
    }

    return {
        avgGuesses: avgGuesses,
        bestBrand: bestBrand,
        bestBrandAvg: bestAvg,
        winStreak: streak,
        totalGames: arr.length,
        totalWins: wins.length
    };
}

function renderStatsModal() {
    const s = computeStats();
    const avgEl = document.getElementById('stat-avg-guesses');
    const bestEl = document.getElementById('stat-best-brand');
    const streakEl = document.getElementById('stat-win-streak');

    avgEl.textContent = s.avgGuesses !== null ? (s.avgGuesses.toFixed(2)) : 'N/A';
    if (s.bestBrand) {
        bestEl.textContent = `${s.bestBrand} (avg. ${s.bestBrandAvg.toFixed(2)} guesses)`;
    } else {
        bestEl.textContent = 'N/A';
    }
    streakEl.textContent = s.winStreak;
}

function recordGameResult(won) {
    // Don't record results when in history mode
    if (isHistoryMode) {
        console.log('History mode: Not recording result');
        return;
    }
    
    try {
        const dayNumber = parseInt(document.getElementById('day-number').textContent.replace('Day #',''));
        const guesses = gameState.guesses ? gameState.guesses.length : currentRow;
        let make = null;
        if (won && gameState.guesses && gameState.guesses.length) {
            const last = gameState.guesses[gameState.guesses.length - 1];
            if (last && last.result && last.result.make) make = last.result.make;
        }
        const entry = { dayNumber: dayNumber, won: !!won, guesses: guesses, make: make };
        saveStatsEntry(entry);
    } catch (e) {
        console.error('Error recording game result', e);
    }
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
        actualCurrentDay = data.day_number; // Store the actual current day
        document.getElementById('day-number').textContent = `Day #${data.day_number}`;
        startCountdown(data.seconds_until_next);
        
        // If car cache is missing, wipe browser cache
        if (!data.cache_loaded) {
            localStorage.removeItem('supercardle_state');
        }
        
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
        await displayCarStats(saved.guesses[i].carName, i, true, saved.guesses[i].result);
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

async function displayCarStats(carName, rowIndex, skipAnimations = false, resultData = null) {
    // Update clue image to show more as we make more guesses
    const clueImg = document.getElementById('clue');
    if (isHistoryMode && historyDayNumber) {
        clueImg.src = `history-clue.png?day=${historyDayNumber}&guess=${rowIndex}&t=${Date.now()}`;
    } else {
        clueImg.src = `clue.png?guess=${rowIndex}&t=${Date.now()}`;
    }
    
    let result = resultData;
    // If resultData is not provided (e.g., first time call), fetch it
    if (!result) {
        const requestBody = { car_name: carName };
        if (isHistoryMode && historyDayNumber) {
            requestBody.day_number = historyDayNumber;
        }
        const response = await fetch('check-guess', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(requestBody)
        });
        result = await response.json();
    }
    
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
        
        // Then set and fade in car name (make with model underneath)
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
        { value: result.comparisons.country.value, status: result.comparisons.country.status, type: 'string' },
        { value: result.comparisons.cylinders.value, status: result.comparisons.cylinders.status, type: 'number' },
        { value: result.comparisons.horsepower.value, status: result.comparisons.horsepower.status, type: 'number' },
        { 
            value: `${result.comparisons.fuel_capacity_gal.value} / ${result.comparisons.fuel_capacity_liters.value}`,
            status: result.comparisons.fuel_capacity_gal.status === result.comparisons.fuel_capacity_liters.status ? result.comparisons.fuel_capacity_gal.status : 'partial',
            type: 'number',
            gal_status: result.comparisons.fuel_capacity_gal.status,
            liters_status: result.comparisons.fuel_capacity_liters.status
        }
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
            } else if (stat.status === 'partial') {
                // Handle fuel capacity with mixed status (gal and liters have different statuses)
                if (stat.gal_status === 'correct' || stat.liters_status === 'correct') {
                    cell.classList.add('partial-correct');
                    cell.innerHTML = stat.value;
                } else {
                    cell.innerHTML = stat.value;
                    cell.classList.add('incorrect');
                }
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
            const colNames = ['model', 'year', 'country', 'cylinders', 'hp', 'fuel'];
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
            { index: 2, col: 'model' },
            { index: 3, col: 'year' },
            { index: 4, col: 'country' },
            { index: 5, col: 'cylinders' },
            { index: 6, col: 'hp' },
            { index: 7, col: 'fuel' }
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
        
        const requestBody = { car_name: guessedCar };
        if (isHistoryMode && historyDayNumber) {
            requestBody.day_number = historyDayNumber;
        }
        const response = await fetch('check-guess', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(requestBody)
        });
        const result = await response.json();

        // Save the full guess result to game state
        gameState.guesses.push({ carName: guessedCar, result: result });
        
        const isCorrect = await displayCarStats(guessedCar, currentRow, false, result);
        
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
            // Record stats and save
            recordGameResult(true);
            saveGameState();
            setTimeout(() => showGameOverModal(true), 1000);
        } else if (currentRow >= maxGuesses) {
            // Lost the game - keep disabled
            gameState.gameOver = true;
            gameState.won = false;
            // Record loss (may not have make info)
            recordGameResult(false);
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
        // Grid: #, Make, Year, Country, Cylinders, Horsepower, Fuel Capacity
        const colMap = [
            { index: 2, col: 'year' },
            { index: 3, col: 'country' },
            { index: 4, col: 'cylinders' },
            { index: 5, col: 'hp' },
            { index: 6, col: 'fuel' }
        ];
        
        colMap.forEach(({ index, col }) => {
            if (!correctColumns.has(col)) {
                const cell = cells[index];
                if (cell && !cell.classList.contains('hint-revealed')) {
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
    const requestBody = { column_name: columnName };
    if (isHistoryMode && historyDayNumber) {
        requestBody.day_number = historyDayNumber;
    }
    const response = await fetch('reveal-hint', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify(requestBody)
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
        'country': 3,
        'cylinders': 4,
        'hp': 5,
        'fuel': 6
    };
    const colIndex = colIndexMap[columnName];
    
    // Apply hint text to current row and all subsequent rows
    for (let i = currentRow; i < maxGuesses; i++) {
        const row = gridRows[i];
        const cell = row.querySelectorAll('.grid-cell')[colIndex];
        if (cell) {
            cell.textContent = value;
            cell.classList.remove('hint-available');
            cell.classList.add('hint-text');
            cell.style.cursor = 'default';
            delete cell.dataset.hintCol;
        }
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

// Function to generate the shareable text
function generateShareText(won) {
    const dayNumber = gameState.dayNumber;
    const guessesTaken = won ? currentRow : 'X';
    
    let shareText = `Supercardle Day #${dayNumber}\n`;
    shareText += `Guess ${guessesTaken}/${maxGuesses}\n\n`;
    
    gameState.guesses.forEach(guess => {
        const result = guess.result;
        let lineEmojis = '';

        // Make comparison
        lineEmojis += result.make_correct ? '🟩' : '⬜'; // White square for incorrect make
        
        // Year comparison
        if (result.comparisons.year.status === 'correct') {
            lineEmojis += '🟩';
        } else if (result.comparisons.year.status === 'higher') {
            lineEmojis += '⬇️'; // Guessed higher than correct
        } else if (result.comparisons.year.status === 'lower') {
            lineEmojis += '⬆️'; // Guessed lower than correct
        } else {
            lineEmojis += '⬜';
        }

        // Country comparison
        lineEmojis += result.comparisons.country.status === 'correct' ? '🟩' : '🟥';
        
        // Cylinders comparison
        if (result.comparisons.cylinders.status === 'correct') {
            lineEmojis += '🟩';
        } else if (result.comparisons.cylinders.status === 'higher') {
            lineEmojis += '⬇️';
        } else if (result.comparisons.cylinders.status === 'lower') {
            lineEmojis += '⬆️';
        } else {
            lineEmojis += '⬜';
        }

        // Horsepower comparison
        if (result.comparisons.horsepower.status === 'correct') {
            lineEmojis += '🟩';
        } else if (result.comparisons.horsepower.status === 'higher') {
            lineEmojis += '⬇️';
        } else if (result.comparisons.horsepower.status === 'lower') {
            lineEmojis += '⬆️';
        } else {
            lineEmojis += '⬜';
        }
        
        // Fuel Capacity comparison (using gal status, which determines the overall status)
        if (result.comparisons.fuel_capacity_gal.status === 'correct' && result.comparisons.fuel_capacity_liters.status === 'correct') {
            lineEmojis += '🟩';
        } else if (result.comparisons.fuel_capacity_gal.status === 'higher') {
            lineEmojis += '⬇️';
        } else if (result.comparisons.fuel_capacity_gal.status === 'lower') {
            lineEmojis += '⬆️';
        } else {
            lineEmojis += '⬜'; // Use white for partial or incorrect fuel capacity
        }
        
        shareText += lineEmojis + '\n';
    });
    shareText += `\nhttps://trigtbh.dev/supercardle`;
    return shareText;
}

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
        const requestBody = {};
        if (isHistoryMode && historyDayNumber) {
            requestBody.day_number = historyDayNumber;
        }
        fetch('reveal-answer', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(requestBody)
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
    // Prevent background controls while modal is open
    document.body.classList.add('modal-open');
}

// Close modal functionality
document.getElementById('close-modal').addEventListener('click', function() {
    const modal = document.getElementById('game-over-modal');
    modal.classList.remove('show');
    document.getElementById('share-feedback').classList.remove('show'); // Hide feedback on close
    // Re-enable background controls
    document.body.classList.remove('modal-open');
});

// Share button functionality
document.getElementById('share-btn').addEventListener('click', async function() {
    const shareText = generateShareText(gameState.won);
    try {
        await navigator.clipboard.writeText(shareText);
        const shareFeedback = document.getElementById('share-feedback');
        shareFeedback.classList.add('show');
        setTimeout(() => {
            shareFeedback.classList.remove('show');
        }, 3000); // Hide feedback after 3 seconds
    } catch (err) {
        console.error('Failed to copy: ', err);
        // Optionally, provide visual feedback for failure to copy
    }
});

// History functions
function renderHistoryModal(page = null) {
    const daysList = document.getElementById('history-days-list');
    daysList.innerHTML = '';
    
    // Get current day and stats - use actualCurrentDay to always show full range
    const currentDay = actualCurrentDay || parseInt(document.getElementById('day-number').textContent.replace('Day #', '').replace(' (History)', ''));
    const stats = loadStats();
    const statsMap = {};
    stats.forEach(s => {
        statsMap[s.dayNumber] = s;
    });
    
    // Calculate pagination
    const totalDays = currentDay;
    const totalPages = Math.ceil(totalDays / DAYS_PER_PAGE);
    
    // If page not specified, calculate based on currently displayed day
    if (page === null) {
        const displayedDay = isHistoryMode ? historyDayNumber : actualCurrentDay;
        page = Math.floor((displayedDay - 1) / DAYS_PER_PAGE);
    }
    
    historyPage = Math.max(0, Math.min(page, totalPages - 1));
    
    // Calculate day range for current page (showing oldest first: 1-10, 11-20, etc)
    const startDay = (historyPage * DAYS_PER_PAGE) + 1;
    const endDay = Math.min(totalDays, startDay + DAYS_PER_PAGE - 1);
    
    // Show days for current page (ascending order)
    for (let day = startDay; day <= endDay; day++) {
        const btn = document.createElement('button');
        btn.className = 'history-day-btn';
        btn.textContent = `Day ${day}`;
        
        // Mark if already played
        if (statsMap[day]) {
            if (statsMap[day].won) {
                btn.classList.add('won');
                btn.title = `Won in ${statsMap[day].guesses} guesses`;
            } else {
                btn.classList.add('lost');
                btn.title = 'Lost';
            }
        }
        
        // Highlight the actual current day
        if (day === actualCurrentDay) {
            btn.classList.add('current');
        }
        
        btn.addEventListener('click', () => loadHistoricalDay(day));
        daysList.appendChild(btn);
    }
    
    // Add pagination controls
    const paginationDiv = document.createElement('div');
    paginationDiv.className = 'history-pagination';
    
    const prevBtn = document.createElement('button');
    prevBtn.className = 'history-nav-btn';
    prevBtn.textContent = '← Older';
    prevBtn.disabled = historyPage === 0;
    prevBtn.addEventListener('click', () => renderHistoryModal(historyPage - 1));
    
    const pageInfo = document.createElement('span');
    pageInfo.className = 'history-page-info';
    pageInfo.textContent = `Page ${historyPage + 1} of ${totalPages}`;
    
    const nextBtn = document.createElement('button');
    nextBtn.className = 'history-nav-btn';
    nextBtn.textContent = 'Newer →';
    nextBtn.disabled = historyPage === totalPages - 1;
    nextBtn.addEventListener('click', () => renderHistoryModal(historyPage + 1));
    
    paginationDiv.appendChild(prevBtn);
    paginationDiv.appendChild(pageInfo);
    paginationDiv.appendChild(nextBtn);
    
    daysList.appendChild(paginationDiv);
}

async function loadHistoricalDay(dayNumber) {
    // Use the stored actualCurrentDay
    if (dayNumber === actualCurrentDay && !isHistoryMode) {
        // Already on current day, just close modal
        document.getElementById('history-modal').classList.remove('show');
        document.body.classList.remove('modal-open');
        return;
    }
    
    if (dayNumber === actualCurrentDay && isHistoryMode) {
        // Return to current day - reload page
        location.reload();
        return;
    }
    
    // Close modal
    document.getElementById('history-modal').classList.remove('show');
    document.body.classList.remove('modal-open');
    
    // Hide clue image temporarily and show loading state
    const clueImg = document.getElementById('clue');
    if (clueImg) {
        clueImg.style.opacity = '0.3';
        clueImg.alt = 'Loading...';
    }
    
    // Set history mode
    isHistoryMode = true;
    historyDayNumber = dayNumber;
    
    // Update day display
    document.getElementById('day-number').textContent = `Day #${dayNumber} (History)`;
    
    // Clear game state
    currentRow = 0;
    hintsAvailable = 0;
    hintsUsed = 0;
    correctColumns.clear();
    correctCarName = null;
    gameState = {
        dayNumber: dayNumber,
        guesses: [],
        currentRow: 0,
        hintsUsed: 0,
        hintsAvailable: 0,
        correctColumns: [],
        gameOver: false,
        won: false
    };
    
    // Clear grid
    const gridRows = document.querySelectorAll('.grid-row');
    gridRows.forEach(row => {
        const cells = row.querySelectorAll('.grid-cell');
        cells.forEach((cell, idx) => {
            if (idx > 0) { // Skip guess number cell
                cell.textContent = '';
                cell.className = 'grid-cell';
                if (idx === 1) cell.classList.add('car-name');
            }
        });
    });
    
    // Reset input
    document.getElementById('car-input').value = '';
    document.getElementById('car-input').disabled = false;
    document.getElementById('enter-btn').disabled = true;
    
    // Show clue image for historical day
    const clueContainer = document.querySelector('.clue-image');
    if (clueContainer) {
        clueContainer.style.display = 'block';
    }
    
    // Load the initial clue image for this historical day
    if (clueImg) {
        clueImg.src = `history-clue.png?day=${dayNumber}&guess=0&t=${Date.now()}`;
        // Restore opacity when image loads
        clueImg.onload = () => {
            clueImg.style.opacity = '1';
        };
    }
    
    // Fetch historical car info (to get the correct answer for checking)
    try {
        const response = await fetch(`/history-day/${dayNumber}`);
        const data = await response.json();
        if (data.error) {
            alert('Could not load historical day');
            location.reload();
        }
    } catch (e) {
        console.error('Error loading historical day:', e);
        alert('Could not load historical day');
    }
}

// Stats modal open/close handlers
const statsBtn = document.getElementById('stats-btn');
const statsModal = document.getElementById('stats-modal');
const closeStatsBtn = document.getElementById('close-stats-modal');

if (statsBtn) {
    statsBtn.addEventListener('click', function() {
        renderStatsModal();
        statsModal.classList.add('show');
        document.body.classList.add('modal-open');
    });
}

if (closeStatsBtn) {
    closeStatsBtn.addEventListener('click', function() {
        statsModal.classList.remove('show');
        document.body.classList.remove('modal-open');
    });
}

// Close stats modal when clicking outside content
if (statsModal) {
    statsModal.addEventListener('click', function(e) {
        if (e.target === statsModal) {
            statsModal.classList.remove('show');
            document.body.classList.remove('modal-open');
        }
    });
}

// History modal open/close handlers
const historyBtn = document.getElementById('history-btn');
const historyModal = document.getElementById('history-modal');
const closeHistoryBtn = document.getElementById('close-history-modal');

if (historyBtn) {
    historyBtn.addEventListener('click', function() {
        renderHistoryModal();
        historyModal.classList.add('show');
        document.body.classList.add('modal-open');
    });
}

if (closeHistoryBtn) {
    closeHistoryBtn.addEventListener('click', function() {
        historyModal.classList.remove('show');
        document.body.classList.remove('modal-open');
    });
}

// Close history modal when clicking outside content
if (historyModal) {
    historyModal.addEventListener('click', function(e) {
        if (e.target === historyModal) {
            historyModal.classList.remove('show');
            document.body.classList.remove('modal-open');
        }
    });
}
