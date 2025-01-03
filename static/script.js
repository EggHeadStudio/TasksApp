API_URL = `${window.location.origin}/api`;

// Authenticate the user
async function authenticateUser(name, password) {
    try {
        const response = await fetch(`${API_URL}/authenticate`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name, password })
        });
        if (!response.ok) {
            throw new Error('Authentication failed');
        }
        return await response.json();
    } catch (error) {
        console.error('Error during authentication:', error);
        return null;
    }
}

// Show login modal
function showLoginModal() {
    const modal = document.getElementById('loginModal');
    modal.style.display = 'block';
}

// Hide login modal
function hideLoginModal() {
    const modal = document.getElementById('loginModal');
    modal.style.display = 'none';
}

// Initialize the app after login
async function initializeApp(user) {
    currentUser = user;

    // Hide login modal
    hideLoginModal();

    // Update the UI based on user role
    if (!user.is_admin) {
        document.querySelectorAll('.admin-only').forEach(el => {
            el.style.display = 'none';
        });
    } else {
        document.querySelectorAll('.admin-only').forEach(el => {
            // Show admin-only buttons but leave sections closed
            if (el.tagName === 'BUTTON') {
                el.style.display = 'block';
            }
        });
    }

    // Update the data and views
    await updateCleanerSelect();
    await updateCleanersList();
    await updateWeekView();
    await updateTasksList();
}

// Apply "current-day" class and handle visibility for mobile views
function highlightCurrentDay() {
    const days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];
    const today = new Date().toLocaleDateString('en-US', { weekday: 'long' });
    const dayIndex = days.indexOf(today);

    const tableHeaders = document.querySelectorAll('#weekView th');
    const tableRows = document.querySelectorAll('#weekView tr');

    // Clear existing "current-day" classes
    tableHeaders.forEach(header => header.classList.remove('current-day', 'cleaner'));
    tableRows.forEach(row => {
        const cells = row.children;
        for (let i = 0; i < cells.length; i++) {
            cells[i].classList.remove('current-day', 'cleaner');
        }
    });

    // Apply "cleaner" class to the first column (always visible in portrait mode)
    tableHeaders[0].classList.add('cleaner');
    tableRows.forEach(row => {
        const cells = row.children;
        if (cells[0]) cells[0].classList.add('cleaner');
    });

    // Apply "current-day" class to today's column
    if (dayIndex >= 0) {
        tableHeaders[dayIndex + 1].classList.add('current-day'); // +1 to skip "Cleaners" column
        tableRows.forEach(row => {
            const cells = row.children;
            if (cells[dayIndex + 1]) {
                cells[dayIndex + 1].classList.add('current-day');
            }
        });
    }
}

// Fetch the server IP and initialize the API_URL
async function initializeApiUrl() {
    try {
        console.log('Fetching server IP...');
        const response = await fetch(`${window.location.origin}/api/ip`);
        if (!response.ok) {
            throw new Error('Failed to fetch server IP');
        }
        const data = await response.json();

        // Dynamically set the API URL based on the server response
        API_URL = `${data.ip}/api`;
        console.log('API URL initialized to:', API_URL);

        // Show the login modal on app load
        showLoginModal();
    } catch (error) {
        console.error('Error initializing API URL:', error);
        alert('Failed to initialize the application. Please try again.');
    }
    initializeWebSocket();
}

// Event listener for login form submission
document.getElementById('loginForm').addEventListener('submit', async (e) => {
    e.preventDefault();
    const name = document.getElementById('username').value;
    const password = document.getElementById('password').value;

    const user = await authenticateUser(name, password);
    if (user) {
        await initializeApp(user);
    } else {
        const errorMessage = document.getElementById('loginError');
        errorMessage.style.display = 'block';
        errorMessage.textContent = 'Invalid credentials. Please try again.';
    }
});

// Ensure all collapsible sections are hidden by default
document.querySelectorAll('.collapsible-section').forEach(section => {
    section.classList.remove('active');
    section.style.display = 'none'; // Explicitly hide all sections
});

// Toggle the visibility of a collapsible section
function toggleSection(sectionId) {
    const section = document.getElementById(sectionId);
    const isActive = section.classList.contains('active');
    
    // Close all sections first
    document.querySelectorAll('.collapsible-section').forEach(sec => {
        sec.classList.remove('active');
        sec.style.display = 'none';
    });

    // Toggle the clicked section
    if (!isActive) {
        section.classList.add('active');
        section.style.display = 'block';
    }
}

// Update the QR code dynamically
async function updateQrCode() {
    const qrCodeImg = document.getElementById('qr-code');

    // Fetch the QR code dynamically from the server
    qrCodeImg.src = `${API_URL.replace('/api', '')}/api/qr?t=${Date.now()}`;
}

// Update the QR code for dynamic ip
//async function updateQrCode() {
//    const qrCodeImg = document.getElementById('qr-code');
//    qrCodeImg.src = `${API_URL.replace('/api', '/api/qr')}?t=${Date.now()}`;
//}

// Initialize WebSocket for real-time updates
function initializeWebSocket() {
    const socket = io();

    // Listen for 'update' events from the server
    socket.on('update', async () => {
        console.log('Received update from server.');
        await updateCleanerSelect();
        await updateCleanersList();
        await updateWeekView();
        await updateTasksList();
    });
}

// Fetch cleaners from the API
async function fetchCleaners() {
    try {
        const response = await fetch(`${API_URL}/cleaners`);
        if (!response.ok) {
            console.error('Error fetching cleaners:', response.statusText);
            return [];
        }
        return await response.json();
    } catch (error) {
        console.error('Network error fetching cleaners:', error);
        return [];
    }
}

// Fetch tasks with filtering for non-admin users
async function fetchTasks() {
    try {
        const cleanerIdParam = currentUser && !currentUser.is_admin ? `?cleaner_id=${currentUser.cleaner_id}` : '';
        const response = await fetch(`${API_URL}/tasks${cleanerIdParam}`);
        if (!response.ok) {
            console.error('Error fetching tasks:', response.statusText);
            return [];
        }
        return await response.json();
    } catch (error) {
        console.error('Network error fetching tasks:', error);
        return [];
    }
}

// Add a new cleaner
async function addCleaner(name) {
    try {
        const response = await fetch(`${API_URL}/cleaners`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name })
        });
        if (!response.ok) {
            const errorData = await response.json();
            console.error('Error adding cleaner:', errorData.error || response.statusText);
            return null;
        }
        return await response.json();
    } catch (error) {
        console.error('Network error adding cleaner:', error);
        return null;
    }
}

// Delete a cleaner
async function deleteCleaner(cleaner_id) {
    try {
        const response = await fetch(`${API_URL}/cleaners?id=${cleaner_id}`, { method: 'DELETE' });
        if (!response.ok) {
            console.error('Error deleting cleaner:', response.statusText);
            return false;
        }
        return true;
    } catch (error) {
        console.error('Network error deleting cleaner:', error);
        return false;
    }
}

// Add a new task
async function addTask(cleaner_id, day, task) {
    try {
        const response = await fetch(`${API_URL}/tasks`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ cleaner_id, day, task })
        });
        if (!response.ok) {
            const errorData = await response.json();
            console.error('Error adding task:', errorData.error || response.statusText);
            return null;
        }
        return await response.json();
    } catch (error) {
        console.error('Network error adding task:', error);
        return null;
    }
}

// Delete a task
async function deleteTask(task_id) {
    try {
        const response = await fetch(`${API_URL}/tasks?id=${task_id}`, { method: 'DELETE' });
        if (!response.ok) {
            console.error('Error deleting task:', response.statusText);
            return false;
        }
        return true;
    } catch (error) {
        console.error('Network error deleting task:', error);
        return false;
    }
}

// Update task completion status
async function updateTaskStatus(task_id, completed) {
    try {
        const response = await fetch(`${API_URL}/tasks`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ id: task_id, completed })
        });
        if (!response.ok) {
            console.error('Error updating task status:', response.statusText);
            return false;
        }
        return true;
    } catch (error) {
        console.error('Network error updating task status:', error);
        return false;
    }
}

// Update the cleaner dropdown
async function updateCleanerSelect() {
    const cleaners = await fetchCleaners();
    const select = document.getElementById('cleanerSelect');
    const addTaskButton = document.getElementById('addTaskButton');

    if (cleaners.length) {
        select.innerHTML = cleaners.map(cleaner =>
            `<option value="${cleaner.id}">${cleaner.name}</option>`
        ).join('');
        addTaskButton.disabled = false; // Enable "Add Task" button
    } else {
        select.innerHTML = '<option value="" disabled selected>No cleaners available</option>';
        addTaskButton.disabled = true; // Disable "Add Task" button
    }
}

// Update the cleaner management list
async function updateCleanersList() {
    const cleaners = await fetchCleaners();
    const cleanersList = document.getElementById('cleanersList');
    cleanersList.innerHTML = cleaners.map(cleaner =>
        `<div>
            ${cleaner.name}
            <button class="delete-button" onclick="removeCleaner(${cleaner.id})">Delete</button>
        </div>`
    ).join('');
}

// Update the week view table
async function updateWeekView() {
    const cleaners = await fetchCleaners();
    const tasks = await fetchTasks();
    const tbody = document.querySelector('#weekView tbody');
    tbody.innerHTML = '';

    cleaners.forEach(cleaner => {
        // If the user is not an admin, only show their row
        if (currentUser && !currentUser.is_admin && cleaner.id !== currentUser.cleaner_id) {
            return;
        }

        const row = document.createElement('tr');
        row.innerHTML = `<td>${cleaner.name}</td>` +
            ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
            .map(day => {
                const dayTasks = tasks.filter(task =>
                    task.cleaner === cleaner.name && task.day === day
                );
                return `<td>
                    ${dayTasks.map(task =>
                        `<div class="${task.completed ? 'completed-task' : ''}">
                            <input type="checkbox" ${task.completed ? 'checked' : ''} 
                                onchange="toggleTaskStatus(${task.id}, this.checked)">
                            ${task.task}
                        </div>`
                    ).join('')}
                </td>`;
            }).join('');
        tbody.appendChild(row);
    });
    highlightCurrentDay();
}

// Update the task management list
async function updateTasksList() {
    const tasks = await fetchTasks();
    const tasksList = document.getElementById('tasksList');
    tasksList.innerHTML = tasks.map(task =>
        `<div>
            ${task.task} (${task.cleaner}, ${task.day})
            <button class="delete-button" onclick="removeTask(${task.id})">Delete</button>
        </div>`
    ).join('');
}

// Remove a cleaner
async function removeCleaner(cleaner_id) {
    if (confirm('Are you sure you want to delete this cleaner and all their tasks?')) {
        const success = await deleteCleaner(cleaner_id);
        if (success) {
            alert('Cleaner and tasks deleted successfully.');
            await updateCleanerSelect();
            await updateCleanersList();
            await updateWeekView();
            await updateTasksList();
        } else {
            alert('Failed to delete cleaner. Please try again.');
        }
    }
}

// Remove a task
async function removeTask(task_id) {
    if (confirm('Are you sure you want to delete this task?')) {
        const success = await deleteTask(task_id);
        if (success) {
            alert('Task deleted successfully.');
            await updateWeekView();
            await updateTasksList();
        } else {
            alert('Failed to delete task. Please try again.');
        }
    }
}

// Toggle task completion status
async function toggleTaskStatus(task_id, completed) {
    const success = await updateTaskStatus(task_id, completed);
    if (success) {
        await updateWeekView();
        await updateTasksList();
    } else {
        alert('Failed to update task status. Please try again.');
    }
}

// Add event listeners for forms
document.getElementById('addCleanerForm').addEventListener('submit', async (e) => {
    e.preventDefault();
    const name = document.getElementById('cleanerName').value;
    const result = await addCleaner(name);
    if (result) {
        document.getElementById('cleanerName').value = '';
        await updateCleanerSelect();
        await updateCleanersList();
        await updateWeekView();
    } else {
        alert('Failed to add cleaner. Please try again.');
    }
});

document.getElementById('addTaskForm').addEventListener('submit', async (e) => {
    e.preventDefault();
    const cleaner_id = document.getElementById('cleanerSelect').value;
    const day = document.getElementById('daySelect').value;
    const task = document.getElementById('taskDescription').value;
    const result = await addTask(cleaner_id, day, task);
    if (result) {
        document.getElementById('taskDescription').value = '';
        await updateWeekView();
        await updateTasksList();
    } else {
        alert('Failed to add task. Please try again.');
    }
});

// Initialize API URL and load data
initializeApiUrl();