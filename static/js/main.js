/* =================================================================
   MAIN JAVASCRIPT FILE - Sistem Rekomendasi Bundling
   Menggabungkan semua JavaScript untuk semua halaman
   ================================================================= */

// =================================================================
// GLOBAL UTILITIES
// =================================================================

// Function to detect current page
function getCurrentPage() {
    const path = window.location.pathname;
    if (path === '/' || path.includes('index')) return 'index';
    if (path.includes('configure')) return 'configure';
    if (path.includes('product_analysis')) return 'product_analysis';
    if (path.includes('results')) return 'results';
    return 'unknown';
}

// Function to show loading state
function showLoadingState(button, text = 'Loading...') {
    if (!button) return;
    button.disabled = true;
    button.classList.add('btn-loading');
    const originalText = button.innerHTML;
    button.innerHTML = `<i class="fas fa-spinner fa-spin me-2"></i>${text}`;
    return originalText;
}

// Function to hide loading state
function hideLoadingState(button, originalText) {
    if (!button) return;
    button.disabled = false;
    button.classList.remove('btn-loading');
    if (originalText) {
        button.innerHTML = originalText;
    }
}

// =================================================================
// INDEX PAGE FUNCTIONALITY
// =================================================================

function initIndexPage() {
    console.log('Initializing index page...');
    
    const mainAnalysisInput = document.getElementById('main_analysis_file');
    const productMasterInput = document.getElementById('product_master_file');
    const historicalValidationInput = document.getElementById('historical_validation_file');
    const form = document.querySelector('form');
    
    function validateFile(input, required = false) {
        const allowedExtensions = /(\.csv|\.xlsx|\.xls)$/i;
        
        if (!input.files[0] && required) {
            return 'File wajib dipilih';
        }
        
        if (input.files[0] && !allowedExtensions.exec(input.files[0].name)) {
            return 'Format file tidak didukung. Gunakan CSV, XLSX, atau XLS';
        }
        
        if (input.files[0] && input.files[0].size > 50 * 1024 * 1024) { // 50MB
            return 'Ukuran file terlalu besar (maksimal 50MB)';
        }
        
        return null;
    }
    
    function setupFileValidation(input, required = false) {
        if (!input) return;
        
        input.addEventListener('change', function() {
            const error = validateFile(this, required);
            if (error) {
                this.setCustomValidity(error);
                this.classList.add('is-invalid');
            } else {
                this.setCustomValidity('');
                this.classList.remove('is-invalid');
                if (this.files[0]) {
                    this.classList.add('is-valid');
                }
            }
        });
    }
    
    setupFileValidation(mainAnalysisInput, true);
    setupFileValidation(productMasterInput, false);
    setupFileValidation(historicalValidationInput, false);
    
    if (form) {
        form.addEventListener('submit', function(e) {
            const mainError = validateFile(mainAnalysisInput, true);
            const productError = validateFile(productMasterInput, false);
            const historicalError = validateFile(historicalValidationInput, false);
            
            if (mainError) {
                e.preventDefault();
                alert('Error pada file data pesanan: ' + mainError);
                return false;
            }
            
            if (productError) {
                e.preventDefault();
                alert('Error pada file data produk: ' + productError);
                return false;
            }
            
            if (historicalError) {
                e.preventDefault();
                alert('Error pada file data historis: ' + historicalError);
                return false;
            }
            
            const submitBtn = form.querySelector('button[type="submit"]');
            if (submitBtn) {
                showLoadingState(submitBtn, 'Mengupload dan memvalidasi file...');
                
                let uploadedFiles = [];
                if (mainAnalysisInput && mainAnalysisInput.files[0]) uploadedFiles.push('Data Pesanan');
                if (productMasterInput && productMasterInput.files[0]) uploadedFiles.push('Data Produk');
                if (historicalValidationInput && historicalValidationInput.files[0]) uploadedFiles.push('Data Historis');
                
                setTimeout(() => {
                    submitBtn.innerHTML = `<i class="fas fa-spinner fa-spin me-2"></i>Memproses ${uploadedFiles.join(', ')}...`;
                }, 1000);
            }
        });
    }
    
    // Setup file display and card styling
    [mainAnalysisInput, productMasterInput, historicalValidationInput].forEach(input => {
        if (!input) return;
        
        input.addEventListener('change', function() {
            const card = this.closest('.card');
            if (card) {
                if (this.files[0]) {
                    card.style.borderLeft = '4px solid #28a745';
                    const header = card.querySelector('.card-header');
                    if (header) {
                        header.classList.add('bg-light-success');
                    }
                } else {
                    card.style.borderLeft = this.required ? '4px solid #dc3545' : '4px solid #6c757d';
                    const header = card.querySelector('.card-header');
                    if (header) {
                        header.classList.remove('bg-light-success');
                    }
                }
            }
        });
    });
}

// =================================================================
// CONFIGURE PAGE FUNCTIONALITY
// =================================================================

function initConfigurePage() {
    console.log('Initializing configure page...');
    
    // Kolom tanggal sudah ditetapkan sebagai "Created Time"
    const dateColumnValue = "Created Time";
    const startDateSelect = document.getElementById('start_date');
    const endDateSelect = document.getElementById('end_date');
    const previewButton = document.getElementById('previewFilter');
    const dateFilterInfo = document.getElementById('dateFilterInfo');
    const filterInfoText = document.getElementById('filterInfoText');
    
    // Parameter update functions
    const minSupportInput = document.getElementById('min_support');
    const minConfidenceInput = document.getElementById('min_confidence');
    const minLiftInput = document.getElementById('min_lift');
    
    const supportPercentageSpan = document.getElementById('support_percentage');
    const confidencePercentageSpan = document.getElementById('confidence_percentage');
    const liftValueSpan = document.getElementById('lift_value');
    
    // Update parameter displays
    function updateParameterDisplays() {
        if (supportPercentageSpan) {
            supportPercentageSpan.textContent = (parseFloat(minSupportInput.value) * 100).toFixed(1) + '%';
        }
        if (confidencePercentageSpan) {
            confidencePercentageSpan.textContent = (parseFloat(minConfidenceInput.value) * 100).toFixed(1) + '%';
        }
        if (liftValueSpan) {
            liftValueSpan.textContent = parseFloat(minLiftInput.value).toFixed(1);
        }
    }
    
    // Add event listeners for parameter updates
    if (minSupportInput) minSupportInput.addEventListener('input', updateParameterDisplays);
    if (minConfidenceInput) minConfidenceInput.addEventListener('input', updateParameterDisplays);
    if (minLiftInput) minLiftInput.addEventListener('input', updateParameterDisplays);
    
    // Function to normalize number format (convert comma to dot)
    function normalizeNumberInput(input) {
        if (!input) return;
        input.addEventListener('blur', function() {
            // Convert comma to dot for decimal separator
            this.value = this.value.replace(',', '.');
            updateParameterDisplays();
        });
    }
    
    // Apply normalization to all number inputs
    normalizeNumberInput(minSupportInput);
    normalizeNumberInput(minConfidenceInput);
    normalizeNumberInput(minLiftInput);
    
    // Add form submission handler to ensure proper format
    const form = document.querySelector('form');
    if (form) {
        form.addEventListener('submit', function(e) {
            // Ensure all numeric inputs use dot as decimal separator
            if (minSupportInput) minSupportInput.value = minSupportInput.value.replace(',', '.');
            if (minConfidenceInput) minConfidenceInput.value = minConfidenceInput.value.replace(',', '.');
            if (minLiftInput) minLiftInput.value = minLiftInput.value.replace(',', '.');
            
            // Validate ranges
            const support = parseFloat(minSupportInput ? minSupportInput.value : 0);
            const confidence = parseFloat(minConfidenceInput ? minConfidenceInput.value : 0);
            const lift = parseFloat(minLiftInput ? minLiftInput.value : 0);
            
            if (minSupportInput && (support < 0.001 || support > 1)) {
                alert('Minimum Support harus antara 0.001 dan 1');
                e.preventDefault();
                return false;
            }
            
            if (minConfidenceInput && (confidence < 0.1 || confidence > 1)) {
                alert('Minimum Confidence harus antara 0.1 dan 1');
                e.preventDefault();
                return false;
            }
            
            if (minLiftInput && lift < 1) {
                alert('Minimum Lift harus >= 1');
                e.preventDefault();
                return false;
            }
            
            console.log('Form submitted with parameters:');
            console.log('Support:', support);
            console.log('Confidence:', confidence);
            console.log('Lift:', lift);
        });
    }
    
    let uniqueDates = [];
    let totalRecords = 0;
    
    // Function to show loading modal
    function showLoading() {
        const loadingModal = document.getElementById('loadingModal');
        if (loadingModal && typeof bootstrap !== 'undefined') {
            const modal = new bootstrap.Modal(loadingModal);
            modal.show();
        }
    }
    
    // Function to hide loading modal
    function hideLoading() {
        const loadingModal = document.getElementById('loadingModal');
        if (loadingModal && typeof bootstrap !== 'undefined') {
            const modal = bootstrap.Modal.getInstance(loadingModal);
            if (modal) modal.hide();
        }
    }
    
    // Function to load unique dates from server
    async function loadUniqueDates(columnName) {
        showLoading();
        
        try {
            const response = await fetch('/get_unique_dates', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    column: columnName
                })
            });
            
            if (!response.ok) {
                throw new Error('Network response was not ok');
            }
            
            const data = await response.json();
            
            if (data.success) {
                // Filter out nilai "order" dan nilai tidak valid dari hasil server
                uniqueDates = data.dates.filter(date => {
                    return date && 
                           date.toLowerCase() !== 'order' && 
                           date.length > 5 && 
                           /\d/.test(date);
                }).sort();
                
                totalRecords = data.total_records;
                
                // Populate date selects
                populateDateSelects();
                
                // Show success message
                console.log(`Berhasil memuat ${uniqueDates.length} tanggal unik dari kolom ${columnName}`);
            } else {
                console.error('Error loading dates:', data.error);
                alert('Error memuat data tanggal: ' + data.error);
            }
        } catch (error) {
            console.error('Error loading dates:', error);
            alert('Terjadi kesalahan saat memuat data tanggal');
        }
        
        hideLoading();
    }
    
    // Function to populate date select options
    function populateDateSelects() {
        if (!startDateSelect || !endDateSelect) return;
        
        // Clear existing options
        startDateSelect.innerHTML = '<option value="">Pilih tanggal mulai...</option>';
        endDateSelect.innerHTML = '<option value="">Pilih tanggal akhir...</option>';
        
        // Add unique dates as options
        uniqueDates.forEach(date => {
            const option1 = new Option(date, date);
            const option2 = new Option(date, date);
            startDateSelect.add(option1);
            endDateSelect.add(option2);
        });
        
        // Set default values (first and last date)
        if (uniqueDates.length > 0) {
            // Set tanggal mulai ke tanggal pertama
            startDateSelect.value = uniqueDates[0];
            // Set tanggal akhir ke tanggal terakhir (nilai unik terakhir)
            endDateSelect.value = uniqueDates[uniqueDates.length - 1];
            
            // Auto preview dengan data default
            setTimeout(() => {
                previewFilter();
            }, 500);
        }
    }
    
    // Function to preview filter results
    async function previewFilter() {
        const columnName = dateColumnValue;
        const startDate = startDateSelect ? startDateSelect.value : '';
        const endDate = endDateSelect ? endDateSelect.value : '';
        
        if (!filterInfoText) return;
        
        if (!startDate || !endDate) {
            // Jika tidak ada tanggal dipilih, tampilkan info bahwa semua data akan digunakan
            filterInfoText.innerHTML = `
                <strong>Mode: Semua Data</strong><br>
                Tidak ada filter tanggal yang dipilih. Semua <strong>${totalRecords}</strong> record akan diproses.
            `;
            if (dateFilterInfo) {
                dateFilterInfo.className = 'alert alert-warning';
                dateFilterInfo.classList.remove('d-none');
            }
            return;
        }
        
        if (startDate > endDate) {
            alert('Tanggal mulai tidak boleh lebih besar dari tanggal akhir');
            return;
        }
        
        showLoading();
        
        try {
            const response = await fetch('/preview_date_filter', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    column: columnName,
                    start_date: startDate,
                    end_date: endDate
                })
            });
            
            if (!response.ok) {
                throw new Error('Network response was not ok');
            }
            
            const data = await response.json();
            
            if (data.success) {
                const filteredCount = data.filtered_count;
                const percentage = ((filteredCount / totalRecords) * 100).toFixed(1);
                
                filterInfoText.innerHTML = `
                    <strong>Mode: Filter Aktif</strong><br>
                    Rentang tanggal <strong>${startDate}</strong> hingga <strong>${endDate}</strong> 
                    akan memproses <strong>${filteredCount}</strong> dari ${totalRecords} record (${percentage}%)
                `;
                if (dateFilterInfo) {
                    dateFilterInfo.className = 'alert alert-success';
                    dateFilterInfo.classList.remove('d-none');
                }
            } else {
                alert('Error: ' + data.error);
            }
        } catch (error) {
            console.error('Error previewing filter:', error);
            alert('Terjadi kesalahan saat preview filter');
        }
        
        hideLoading();
    }
    
    // Event listeners
    if (previewButton) {
        previewButton.addEventListener('click', previewFilter);
    }
    
    // Event listener untuk perubahan tanggal
    if (startDateSelect) {
        startDateSelect.addEventListener('change', function() {
            if (startDateSelect.value && endDateSelect && endDateSelect.value) {
                previewFilter();
            }
        });
    }
    
    if (endDateSelect) {
        endDateSelect.addEventListener('change', function() {
            if (endDateSelect.value && startDateSelect && startDateSelect.value) {
                previewFilter();
            }
        });
    }
    
    // Auto-load dates untuk kolom "Created Time"
    loadUniqueDates(dateColumnValue);
    
    // Initialize parameter displays
    updateParameterDisplays();
}

// =================================================================
// PRODUCT ANALYSIS PAGE FUNCTIONALITY
// =================================================================

function initProductAnalysisPage() {
    console.log('Initializing product analysis page...');
    
    // Initialize search functionality untuk input yang ada placeholder 'Cari produk'
    const searchInputs = document.querySelectorAll('input[placeholder*="Cari produk"]');
    console.log('Found search inputs:', searchInputs.length);
    
    searchInputs.forEach((input, index) => {
        console.log(`Setting up search for input ${index}:`, input.placeholder);
        
        // Determine table ID based on placeholder text
        let tableId;
        if (input.placeholder.includes('terjual') && !input.placeholder.includes('tidak')) {
            tableId = 'soldProductsTable';
        } else if (input.placeholder.includes('tidak terjual')) {
            tableId = 'unsoldProductsTable';
        }
        
        if (tableId) {
            input.addEventListener('keyup', function() {
                console.log(`Searching in ${tableId} with value:`, this.value);
                searchTable(tableId, this.value);
            });
            
            // Also add input event for better responsiveness
            input.addEventListener('input', function() {
                searchTable(tableId, this.value);
            });
            
            console.log(`Search listener added for ${tableId}`);
        }
    });
    
    // Alternative: Set up search by finding inputs within specific cards
    const soldProductCard = document.querySelector('#soldProductsTable')?.closest('.card');
    const unsoldProductCard = document.querySelector('#unsoldProductsTable')?.closest('.card');
    
    if (soldProductCard) {
        const soldSearchInput = soldProductCard.querySelector('input[type="text"]');
        if (soldSearchInput && !soldSearchInput.hasAttribute('data-search-setup')) {
            soldSearchInput.setAttribute('data-search-setup', 'true');
            soldSearchInput.addEventListener('keyup', function() {
                searchTable('soldProductsTable', this.value);
            });
            soldSearchInput.addEventListener('input', function() {
                searchTable('soldProductsTable', this.value);
            });
            console.log('Sold products search setup completed');
        }
    }
    
    if (unsoldProductCard) {
        const unsoldSearchInput = unsoldProductCard.querySelector('input[type="text"]');
        if (unsoldSearchInput && !unsoldSearchInput.hasAttribute('data-search-setup')) {
            unsoldSearchInput.setAttribute('data-search-setup', 'true');
            unsoldSearchInput.addEventListener('keyup', function() {
                searchTable('unsoldProductsTable', this.value);
            });
            unsoldSearchInput.addEventListener('input', function() {
                searchTable('unsoldProductsTable', this.value);
            });
            console.log('Unsold products search setup completed');
        }
    }
    
    // Add smooth scrolling for better UX
    document.querySelectorAll('a[href^="#"]').forEach(anchor => {
        anchor.addEventListener('click', function (e) {
            e.preventDefault();
            const target = document.querySelector(this.getAttribute('href'));
            if (target) {
                target.scrollIntoView({
                    behavior: 'smooth'
                });
            }
        });
    });
    
    console.log('Product analysis page initialization completed');
}

// Search function for product analysis tables
function searchTable(tableId, searchValue) {
    console.log(`Searching table ${tableId} with value: "${searchValue}"`);
    
    const table = document.getElementById(tableId);
    if (!table) {
        console.error(`Table with ID ${tableId} not found`);
        return;
    }
    
    const rows = table.querySelectorAll('tbody tr');
    console.log(`Found ${rows.length} rows to search`);
    
    searchValue = searchValue.toLowerCase().trim();
    
    let visibleCount = 0;
    rows.forEach((row, index) => {
        const text = row.textContent.toLowerCase();
        if (searchValue === '' || text.includes(searchValue)) {
            row.style.display = '';
            visibleCount++;
        } else {
            row.style.display = 'none';
        }
    });
    
    console.log(`Search completed. ${visibleCount} rows visible out of ${rows.length}`);
    
    // Optional: Show no results message
    const tableContainer = table.closest('.table-responsive') || table.parentElement;
    let noResultsMsg = tableContainer.querySelector('.no-results-message');
    
    if (visibleCount === 0 && searchValue !== '') {
        if (!noResultsMsg) {
            noResultsMsg = document.createElement('div');
            noResultsMsg.className = 'no-results-message text-center p-3 text-muted';
            noResultsMsg.innerHTML = '<i class="fas fa-search me-2"></i>Tidak ada hasil yang ditemukan';
            tableContainer.appendChild(noResultsMsg);
        }
        noResultsMsg.style.display = 'block';
    } else {
        if (noResultsMsg) {
            noResultsMsg.style.display = 'none';
        }
    }
}

// Export table to CSV function
function exportTable(tableId, filename) {
    const table = document.getElementById(tableId);
    if (!table) return;
    
    const rows = table.querySelectorAll('tr');
    const csv = [];
    
    for (let i = 0; i < rows.length; i++) {
        const row = [];
        const cols = rows[i].querySelectorAll('td, th');
        
        for (let j = 0; j < cols.length; j++) {
            let text = cols[j].innerText.trim();
            // Handle CSV escaping
            text = text.replace(/"/g, '""');
            if (text.includes(',') || text.includes('\n')) {
                text = '"' + text + '"';
            }
            row.push(text);
        }
        
        csv.push(row.join(','));
    }
    
    // Download CSV
    const csvString = csv.join('\n');
    const BOM = "\uFEFF"; // BOM for UTF-8
    const csvBlob = new Blob([BOM + csvString], {type: "text/csv;charset=utf-8;"});
    
    const downloadLink = document.createElement("a");
    downloadLink.download = filename;
    downloadLink.href = window.URL.createObjectURL(csvBlob);
    downloadLink.style.display = "none";
    
    document.body.appendChild(downloadLink);
    downloadLink.click();
    
    setTimeout(function() {
        document.body.removeChild(downloadLink);
        window.URL.revokeObjectURL(downloadLink.href);
    }, 500);
}

// =================================================================
// RESULTS PAGE FUNCTIONALITY
// =================================================================

function initResultsPage() {
    console.log('Initializing results page...');
    
    // Check if jQuery and DataTable are available
    if (typeof $ !== 'undefined' && $.fn.DataTable) {
        initDataTable();
    } else {
        console.warn('jQuery or DataTables not available, skipping DataTable initialization');
    }
    
    // Initialize other results page functionality
    initResultsPageEvents();
}

function initDataTable() {
    console.log("Results page initialized with DataTable");
    
    var liftColumnIndex = 5;
    
    // Inisialisasi DataTable
    $('#rulesTable').DataTable({
        order: [[liftColumnIndex, 'desc']], 
        pageLength: 10,
        columnDefs: [
            {
               targets: 0,
                orderable: false
            },
            {
               targets: [3, 4, 5], 
                type: 'num'
            }
        ],
        language: {
            search: "Cari:",
            lengthMenu: "Tampilkan _MENU_ entri",
            info: "Menampilkan _START_ sampai _END_ dari _TOTAL_ entri",
            infoEmpty: "Menampilkan 0 sampai 0 dari 0 entri",
            infoFiltered: "(disaring dari _MAX_ total entri)",
            paginate: {
                first: "Pertama",
                last: "Terakhir",
                next: "Selanjutnya",
                previous: "Sebelumnya"
            }
        },
        drawCallback: function(settings) {
            console.log('DataTable redrawn with ' + this.api().rows().count() + ' rows');
            this.api().column(0, {page: 'current'}).nodes().each(function(cell, i) {
                cell.innerHTML = i + 1;
            });
        }
    });
    
    // Renumber on sort
    $('#rulesTable').on('order.dt', function() {
        var table = $('#rulesTable').DataTable();
        table.column(0, {page: 'current'}).nodes().each(function(cell, i) {
            cell.innerHTML = i + 1;
        });
    });
}

function initResultsPageEvents() {
    // Smooth scrolling for anchors
    document.querySelectorAll('a[href^="#"]').forEach(anchor => {
        anchor.addEventListener('click', function(e) {
            e.preventDefault();
            const target = document.querySelector(this.getAttribute('href'));
            if (target) {
                target.scrollIntoView({
                    behavior: 'smooth',
                    block: 'start'
                });
            }
        });
    });
    
    // Initialize tooltips if Bootstrap is available
    if (typeof bootstrap !== 'undefined') {
        var tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
        var tooltipList = tooltipTriggerList.map(function (tooltipTriggerEl) {
            return new bootstrap.Tooltip(tooltipTriggerEl);
        });
    }
    
    // Add hover effects to metric cards
    const metricCards = document.querySelectorAll('.metric-card');
    metricCards.forEach(card => {
        card.addEventListener('mouseenter', function() {
            this.classList.add('shadow-lg');
        });
        
        card.addEventListener('mouseleave', function() {
            this.classList.remove('shadow-lg');
        });
    });
    
    // Add click handler for rule items in recommendation section
    const listGroupItems = document.querySelectorAll('.list-group-item-action');
    listGroupItems.forEach(item => {
        item.addEventListener('click', function(e) {
            e.preventDefault();
            // Scroll to full table
            var fullTable = document.getElementById('fullRulesTable');
            if (fullTable) {
                fullTable.scrollIntoView({
                    behavior: 'smooth',
                    block: 'start'
                });
            }
        });
    });
}

// =================================================================
// MAIN INITIALIZATION
// =================================================================

document.addEventListener('DOMContentLoaded', function() {
    console.log('Main.js loaded, initializing...');
    
    const currentPage = getCurrentPage();
    console.log('Current page detected:', currentPage);
    
    // Initialize based on current page
    switch (currentPage) {
        case 'index':
            initIndexPage();
            break;
        case 'configure':
            initConfigurePage();
            break;
        case 'product_analysis':
            initProductAnalysisPage();
            break;
        case 'results':
            initResultsPage();
            break;
        default:
            console.log('Page not recognized, applying general initialization');
            // General initialization for unknown pages
            initGeneralFeatures();
            break;
    }
    
    // Always apply general features
    initGeneralFeatures();
});

// =================================================================
// GENERAL FEATURES (APPLIED TO ALL PAGES)
// =================================================================

function initGeneralFeatures() {
    console.log('Initializing general features...');
    
    // Add smooth scrolling to all anchor links
    document.querySelectorAll('a[href^="#"]').forEach(anchor => {
        anchor.addEventListener('click', function (e) {
            e.preventDefault();
            const target = document.querySelector(this.getAttribute('href'));
            if (target) {
                target.scrollIntoView({
                    behavior: 'smooth'
                });
            }
        });
    });
    
    // Auto-hide alerts after 5 seconds
    const alerts = document.querySelectorAll('.alert.alert-dismissible');
    alerts.forEach(alert => {
        setTimeout(() => {
            if (alert.parentNode) {
                alert.classList.add('fade');
                setTimeout(() => {
                    if (alert.parentNode) {
                        alert.remove();
                    }
                }, 150);
            }
        }, 5000);
    });
    
    // Add loading state to all form submissions
    const forms = document.querySelectorAll('form');
    forms.forEach(form => {
        form.addEventListener('submit', function() {
            const submitBtn = this.querySelector('button[type="submit"], input[type="submit"]');
            if (submitBtn && !submitBtn.disabled) {
                showLoadingState(submitBtn, 'Processing...');
            }
        });
    });
    
    // Initialize card hover effects
    const cards = document.querySelectorAll('.card');
    cards.forEach(card => {
        card.addEventListener('mouseenter', function() {
            this.style.transform = 'translateY(-2px)';
        });
        
        card.addEventListener('mouseleave', function() {
            this.style.transform = 'translateY(0)';
        });
    });
    
    console.log('General features initialized');
}

// =================================================================
// GLOBAL FUNCTIONS (ACCESSIBLE FROM HTML)
// =================================================================

// Make functions globally accessible for backward compatibility
window.searchTable = searchTable;
window.exportTable = exportTable;
window.showLoadingState = showLoadingState;
window.hideLoadingState = hideLoadingState;

console.log('Main.js fully loaded and ready');