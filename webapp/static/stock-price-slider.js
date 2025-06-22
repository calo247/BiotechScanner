// Stock price range slider component
class StockPriceRangeSlider {
    constructor(container, options = {}) {
        this.container = container;
        this.minValue = options.min || 0;
        this.maxValue = options.max || 1000; // $1000 max
        this.currentMin = options.currentMin || this.minValue;
        this.currentMax = options.currentMax || this.maxValue;
        this.onChange = options.onChange || (() => {});
        
        // Linear scale points for stock prices
        this.scalePoints = [
            { value: 0, label: '$0', position: 0 },
            { value: 1, label: '$1', position: 10 },
            { value: 5, label: '$5', position: 20 },
            { value: 10, label: '$10', position: 30 },
            { value: 25, label: '$25', position: 40 },
            { value: 50, label: '$50', position: 50 },
            { value: 100, label: '$100', position: 60 },
            { value: 200, label: '$200', position: 70 },
            { value: 500, label: '$500', position: 80 },
            { value: 750, label: '$750', position: 90 },
            { value: 1000, label: '$1000', position: 100 }
        ];
        
        this.init();
    }
    
    init() {
        // Create HTML structure
        this.container.innerHTML = `
            <div class="stock-price-slider">
                <div class="slider-header">
                    <span class="slider-label">Stock Price Range:</span>
                    <button class="reset-button" title="Reset to full range">Reset</button>
                </div>
                <div class="slider-main">
                    <div class="slider-inputs">
                        <input type="text" class="stock-price-input min-input" 
                               placeholder="0" 
                               value="${this.formatValue(this.currentMin)}">
                        <span class="separator">to</span>
                        <input type="text" class="stock-price-input max-input" 
                               placeholder="1,000" 
                               value="${this.formatValue(this.currentMax)}">
                    </div>
                    <div class="slider-container">
                        <div class="slider-track"></div>
                        <div class="slider-range"></div>
                        <div class="slider-handle min-handle" data-handle="min"></div>
                        <div class="slider-handle max-handle" data-handle="max"></div>
                    </div>
                </div>
            </div>
        `;
        
        // Get elements
        this.elements = {
            minHandle: this.container.querySelector('.min-handle'),
            maxHandle: this.container.querySelector('.max-handle'),
            range: this.container.querySelector('.slider-range'),
            minInput: this.container.querySelector('.min-input'),
            maxInput: this.container.querySelector('.max-input'),
            track: this.container.querySelector('.slider-track'),
            resetButton: this.container.querySelector('.reset-button')
        };
        
        // Set initial positions
        this.updatePositions();
        
        // Add event listeners
        this.attachEventListeners();
    }
    
    attachEventListeners() {
        let activeHandle = null;
        let startX = 0;
        let startPosition = 0;
        
        // Handle mouse/touch start
        const handleStart = (e, handle) => {
            activeHandle = handle;
            startX = e.type.includes('mouse') ? e.clientX : e.touches[0].clientX;
            const rect = this.elements.track.getBoundingClientRect();
            
            if (handle === 'min') {
                startPosition = this.valueToPosition(this.currentMin);
            } else {
                startPosition = this.valueToPosition(this.currentMax);
            }
            
            e.preventDefault();
        };
        
        // Handle mouse/touch move
        const handleMove = (e) => {
            if (!activeHandle) return;
            
            const currentX = e.type.includes('mouse') ? e.clientX : e.touches[0].clientX;
            const rect = this.elements.track.getBoundingClientRect();
            const deltaX = currentX - startX;
            const deltaPercent = (deltaX / rect.width) * 100;
            let newPosition = startPosition + deltaPercent;
            
            // Constrain position
            newPosition = Math.max(0, Math.min(100, newPosition));
            
            // Convert position to value
            const newValue = this.positionToValue(newPosition);
            
            if (activeHandle === 'min') {
                this.currentMin = Math.min(newValue, this.currentMax - 0.01); // Min $0.01 difference
            } else {
                this.currentMax = Math.max(newValue, this.currentMin + 0.01);
            }
            
            this.updatePositions();
            this.onChange(this.currentMin, this.currentMax);
        };
        
        // Handle mouse/touch end
        const handleEnd = () => {
            activeHandle = null;
        };
        
        // Mouse events
        this.elements.minHandle.addEventListener('mousedown', (e) => handleStart(e, 'min'));
        this.elements.maxHandle.addEventListener('mousedown', (e) => handleStart(e, 'max'));
        document.addEventListener('mousemove', handleMove);
        document.addEventListener('mouseup', handleEnd);
        
        // Touch events
        this.elements.minHandle.addEventListener('touchstart', (e) => handleStart(e, 'min'));
        this.elements.maxHandle.addEventListener('touchstart', (e) => handleStart(e, 'max'));
        document.addEventListener('touchmove', handleMove);
        document.addEventListener('touchend', handleEnd);
        
        // Click on track to set value
        this.elements.track.addEventListener('click', (e) => {
            const rect = this.elements.track.getBoundingClientRect();
            const clickX = e.clientX - rect.left;
            const clickPercent = (clickX / rect.width) * 100;
            const clickValue = this.positionToValue(clickPercent);
            
            // Move closest handle
            const minDistance = Math.abs(clickValue - this.currentMin);
            const maxDistance = Math.abs(clickValue - this.currentMax);
            
            if (minDistance < maxDistance) {
                this.currentMin = Math.min(clickValue, this.currentMax - 0.01);
            } else {
                this.currentMax = Math.max(clickValue, this.currentMin + 0.01);
            }
            
            this.updatePositions();
            this.onChange(this.currentMin, this.currentMax);
        });
        
        // Reset button
        this.elements.resetButton.addEventListener('click', () => {
            this.currentMin = this.minValue;
            this.currentMax = this.maxValue;
            this.updatePositions();
            this.onChange(this.currentMin, this.currentMax);
        });
        
        // Input box events
        this.elements.minInput.addEventListener('change', (e) => {
            const value = this.parseInputValue(e.target.value);
            if (value !== null && value <= this.currentMax - 0.01) {
                this.currentMin = Math.max(this.minValue, value);
                this.updatePositions();
                this.onChange(this.currentMin, this.currentMax);
            } else {
                // Reset to current value if invalid
                e.target.value = this.formatValue(this.currentMin);
            }
        });
        
        this.elements.maxInput.addEventListener('change', (e) => {
            const value = this.parseInputValue(e.target.value);
            if (value !== null && value >= this.currentMin + 0.01) {
                this.currentMax = Math.min(this.maxValue, value);
                this.updatePositions();
                this.onChange(this.currentMin, this.currentMax);
            } else {
                // Reset to current value if invalid
                e.target.value = this.formatValue(this.currentMax);
            }
        });
        
        // Format on blur
        this.elements.minInput.addEventListener('blur', (e) => {
            e.target.value = this.formatValue(this.currentMin);
        });
        
        this.elements.maxInput.addEventListener('blur', (e) => {
            e.target.value = this.formatValue(this.currentMax);
        });
    }
    
    valueToPosition(value) {
        // Use linear interpolation between scale points
        for (let i = 0; i < this.scalePoints.length - 1; i++) {
            const point1 = this.scalePoints[i];
            const point2 = this.scalePoints[i + 1];
            
            if (value >= point1.value && value <= point2.value) {
                const valueRange = point2.value - point1.value;
                const positionRange = point2.position - point1.position;
                const valueOffset = value - point1.value;
                
                if (valueRange === 0) return point1.position;
                
                const ratio = valueOffset / valueRange;
                return point1.position + (ratio * positionRange);
            }
        }
        
        return value >= this.maxValue ? 100 : 0;
    }
    
    positionToValue(position) {
        // Find the scale points this position falls between
        for (let i = 0; i < this.scalePoints.length - 1; i++) {
            const point1 = this.scalePoints[i];
            const point2 = this.scalePoints[i + 1];
            
            if (position >= point1.position && position <= point2.position) {
                const positionRange = point2.position - point1.position;
                const valueRange = point2.value - point1.value;
                const positionOffset = position - point1.position;
                
                if (positionRange === 0) return point1.value;
                
                const ratio = positionOffset / positionRange;
                return parseFloat((point1.value + (ratio * valueRange)).toFixed(2));
            }
        }
        
        return position >= 100 ? this.maxValue : this.minValue;
    }
    
    updatePositions() {
        const minPos = this.valueToPosition(this.currentMin);
        const maxPos = this.valueToPosition(this.currentMax);
        
        // Update handle positions
        this.elements.minHandle.style.left = `${minPos}%`;
        this.elements.maxHandle.style.left = `${maxPos}%`;
        
        // Update range bar
        this.elements.range.style.left = `${minPos}%`;
        this.elements.range.style.width = `${maxPos - minPos}%`;
        
        // Update input values
        this.elements.minInput.value = this.formatValue(this.currentMin);
        this.elements.maxInput.value = this.formatValue(this.currentMax);
        
        // Show/hide reset button
        const isFullRange = this.currentMin === this.minValue && this.currentMax === this.maxValue;
        this.elements.resetButton.style.display = isFullRange ? 'none' : 'inline-block';
    }
    
    formatValue(value) {
        if (value === 0) return '0';
        return value.toLocaleString('en-US', {
            minimumFractionDigits: value < 1 ? 2 : 0,
            maximumFractionDigits: value < 1 ? 2 : 0
        });
    }
    
    parseInputValue(input) {
        // Remove commas and spaces
        input = input.replace(/[,\s]/g, '').trim();
        
        if (input === '' || input === '0') return 0;
        
        // Check if it's a valid number
        if (!/^\d+(\.\d{1,2})?$/.test(input)) return null;
        
        const value = parseFloat(input);
        
        return isNaN(value) ? null : value;
    }
    
    getValues() {
        return {
            min: this.currentMin,
            max: this.currentMax
        };
    }
    
    setValues(min, max) {
        this.currentMin = Math.max(this.minValue, min);
        this.currentMax = Math.min(this.maxValue, max);
        this.updatePositions();
    }
}