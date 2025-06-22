// Custom double-ended range slider for market cap filtering
class MarketCapRangeSlider {
    constructor(container, options = {}) {
        this.container = container;
        this.minValue = options.min || 0;
        this.maxValue = options.max || 1000000000000; // 1 trillion
        this.currentMin = options.currentMin || this.minValue;
        this.currentMax = options.currentMax || this.maxValue;
        this.onChange = options.onChange || (() => {});
        
        // Logarithmic scale points for better distribution
        this.scalePoints = [
            { value: 0, label: '$0', position: 0 },
            { value: 10000000, label: '$10M', position: 10 },
            { value: 50000000, label: '$50M', position: 20 },
            { value: 100000000, label: '$100M', position: 30 },
            { value: 300000000, label: '$300M', position: 40 },
            { value: 1000000000, label: '$1B', position: 50 },
            { value: 2000000000, label: '$2B', position: 60 },
            { value: 5000000000, label: '$5B', position: 70 },
            { value: 10000000000, label: '$10B', position: 80 },
            { value: 50000000000, label: '$50B', position: 90 },
            { value: 200000000000, label: '$200B', position: 95 },
            { value: 1000000000000, label: '$1T', position: 100 }
        ];
        
        this.init();
    }
    
    init() {
        // Create HTML structure
        this.container.innerHTML = `
            <div class="market-cap-slider">
                <div class="slider-header">
                    <span class="slider-label">Market Cap Range:</span>
                    <span class="slider-values">
                        <span class="min-value">${this.formatValue(this.currentMin)}</span>
                        <span class="separator">-</span>
                        <span class="max-value">${this.formatValue(this.currentMax)}</span>
                    </span>
                    <button class="reset-button" title="Reset to full range">Reset</button>
                </div>
                <div class="slider-container">
                    <div class="slider-track"></div>
                    <div class="slider-range"></div>
                    <div class="slider-handle min-handle" data-handle="min"></div>
                    <div class="slider-handle max-handle" data-handle="max"></div>
                </div>
                <div class="slider-scale">
                    ${this.scalePoints.map(point => `
                        <div class="scale-mark" style="left: ${point.position}%">
                            <div class="scale-tick"></div>
                            <div class="scale-label">${point.label}</div>
                        </div>
                    `).join('')}
                </div>
            </div>
        `;
        
        // Get elements
        this.elements = {
            minHandle: this.container.querySelector('.min-handle'),
            maxHandle: this.container.querySelector('.max-handle'),
            range: this.container.querySelector('.slider-range'),
            minValueDisplay: this.container.querySelector('.min-value'),
            maxValueDisplay: this.container.querySelector('.max-value'),
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
                this.currentMin = Math.min(newValue, this.currentMax - 1000000); // Min $1M difference
            } else {
                this.currentMax = Math.max(newValue, this.currentMin + 1000000);
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
                this.currentMin = Math.min(clickValue, this.currentMax - 1000000);
            } else {
                this.currentMax = Math.max(clickValue, this.currentMin + 1000000);
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
    }
    
    valueToPosition(value) {
        // Use logarithmic interpolation between scale points
        for (let i = 0; i < this.scalePoints.length - 1; i++) {
            const point1 = this.scalePoints[i];
            const point2 = this.scalePoints[i + 1];
            
            if (value >= point1.value && value <= point2.value) {
                const valueRange = point2.value - point1.value;
                const positionRange = point2.position - point1.position;
                const valueOffset = value - point1.value;
                
                if (valueRange === 0) return point1.position;
                
                // Linear interpolation between points
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
                
                // Linear interpolation between points
                const ratio = positionOffset / positionRange;
                return Math.round(point1.value + (ratio * valueRange));
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
        
        // Update value displays
        this.elements.minValueDisplay.textContent = this.formatValue(this.currentMin);
        this.elements.maxValueDisplay.textContent = this.formatValue(this.currentMax);
        
        // Show/hide reset button
        const isFullRange = this.currentMin === this.minValue && this.currentMax === this.maxValue;
        this.elements.resetButton.style.display = isFullRange ? 'none' : 'inline-block';
    }
    
    formatValue(value) {
        if (value === 0) return '$0';
        if (value >= 1e12) return `$${(value / 1e12).toFixed(1)}T`;
        if (value >= 1e9) return `$${(value / 1e9).toFixed(1)}B`;
        if (value >= 1e6) return `$${(value / 1e6).toFixed(0)}M`;
        return `$${(value / 1e3).toFixed(0)}K`;
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