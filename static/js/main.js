// Function to switch tabs and display content
function switchTab(event) {
    const tab = event.target.closest('.tab');
    if (!tab) {
        console.error("No tab found for:", event.target);
        return;
    }

    console.log("Switching tab at:", new Date().toLocaleString('es-ES', { timeZone: 'CET' }), tab);

    // Remove active class from all tabs
    document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
    // Add active class to clicked tab
    tab.classList.add('active');

    const section = tab.getAttribute('data-section');
    const contentArea = document.getElementById('content-area');
    const report = window.currentReport || {}; // Use stored report data

    console.log("Switching to section:", section, "Report data:", report, "Plan raw:", report.plan);

    let content = '';
    switch (section) {
        case 'resumen':
            content = `<h3>Análisis general de la situación política actual</h3><p>${convertBold(report.resumen ? report.resumen.replace(/^\s*-\s*/gm, '').replace('Tendencias generales', '<strong>Tendencias generales</strong>') : 'No hay resumen disponible')}</p>`;
            break;
        case 'analisis':
            const analisisText = report.analisis || '';
            console.log("Analisis text:", analisisText);
            const analisisLines = analisisText.split('\n').filter(line => line.trim());
            content = '<h3>Análisis de Datos</h3><div class="category-list">';
            let currentCategory = null;
            let tweetBuffer = [];
            analisisLines.forEach(line => {
                console.log("Processing line:", line);
                const categoryMatch = line.match(/^(.*?)\s*\((\d+)\s*tweets,\s*Sentimientos:\s*Positivo\s*(\d+),\s*Negativo\s*(\d+),\s*Neutral\s*(\d+)\)/);
                if (categoryMatch) {
                    if (currentCategory) {
                        content += renderCategory(currentCategory, tweetBuffer);
                        tweetBuffer = [];
                    }
                    currentCategory = categoryMatch[1].trim();
                } else if (currentCategory && line.trim().startsWith('-')) {
                    const tweetMatch = line.match(/^\s*-\s*"(.+?)"\s*\((.+?)\)/);
                    if (tweetMatch) {
                        const [__, tweetText, sentimentInfo] = tweetMatch;
                        const sentiment = sentimentInfo.trim();
                        console.log("Matched tweet:", tweetText, "Sentiment:", sentiment, "Full line:", line);
                        tweetBuffer.push({ text: tweetText, sentiment });
                    } else {
                        console.log("No match for tweet line:", line);
                    }
                }
            });
            if (currentCategory) {
                content += renderCategory(currentCategory, tweetBuffer);
            }
            content += '</div>';
            if (!analisisLines.length) content += '<p>No data available for analysis.</p>';
            break;
        case 'plan':
            const planText = report.plan || '';
            console.log("Plan text:", planText);
            const planLines = planText.split('\n').filter(line => line.trim());
            content = '<h3>Plan Estratégico</h3><div class="strategy-list">';
            planLines.forEach(line => {
                const match = line.match(/^([^:]+): Necessidad: (.*?)\s*\(([\d.]+)?%?\s*negativo\)?\.? Propuesta: (.*?)\.? Impacto: (.*?)$/i);
                if (match) {
                    const [_, concept, need, negPercent = 'N/A', proposal, impact] = match;
                    content += `
                        <div class="strategy-card">
                            <div class="strategy-header" onclick="toggleStrategy(event)">
                                <strong>${concept.toUpperCase()}</strong> (${negPercent !== 'N/A' ? `${negPercent}% Negative` : 'No data'})
                                <button class="prioritize-btn" onclick="prioritizeStrategy('${concept.toUpperCase()}', event)">Prioritize</button>
                            </div>
                            <div class="strategy-content">
                                <p><strong>Need:</strong> ${need}</p>
                                <p><strong>Proposal:</strong> ${proposal}</p>
                                <p><strong>Impact:</strong> ${impact}</p>
                            </div>
                        </div>
                    `;
                } else {
                    console.log("No match for plan line:", line);
                }
            });
            content += '</div>';
            if (!planLines.length) content += '<p>No data available for strategic planning.</p>';
            break;
        case 'discurso':
            content = `<h3>Discurso</h3><p>${convertBold(report.discurso || 'No hay discurso disponible')}</p>`;
            break;
        case 'grafico':
            content = `<h3>Gráfico Sugerido</h3><p>${convertBold(report.grafico || 'No gráfico sugerido disponible')}</p><canvas id="chartCanvas"></canvas>`;
            break;
        default:
            content = '<p>Selecciona una sección para ver el contenido.</p>';
    }

    contentArea.innerHTML = content;
    if (section === 'grafico' && window.currentReport?.chart_config) {
        renderChart(window.currentReport.chart_config);
    }
    console.log("Content updated at:", new Date().toLocaleString('es-ES', { timeZone: 'CET' }));
}

// Function to render each category with accordion behavior
function renderCategory(category, tweets) {
    return `
        <div class="category-box">
            <div class="category-header" onclick="toggleCategory(event)">
                <strong>${category.toUpperCase()}</strong> (${tweets.length} tweets)<br>Sentimientos: Positivo ${tweets.filter(t => t.sentiment === 'Positivo').length}, Negativo ${tweets.filter(t => t.sentiment === 'Negativo').length}, Neutral ${tweets.filter(t => t.sentiment === 'Neutral').length}
            </div>
            <div class="category-content">
                <ul class="tweets">
                    ${tweets.map(tweet => `<li class="tweet-item"><span class="tweet-text">${tweet.text}</span> <span class="sentiment">[${tweet.sentiment}]</span></li>`).join('')}
                </ul>
            </div>
        </div>
    `;
}

// Function to toggle category accordion
function toggleCategory(event) {
    const header = event.target.closest('.category-header');
    if (!header) {
        console.error("No category-header found for:", event.target);
        return;
    }
    const box = header.closest('.category-box');
    if (!box) {
        console.error("No category-box found for header:", header);
        return;
    }
    const content = box.querySelector('.category-content');
    if (!content) {
        console.error("No category-content found in box:", box);
        return;
    }

    console.log("Toggling category at:", new Date().toLocaleString('es-ES', { timeZone: 'CET' }), content);

    const isActive = content.classList.contains('active');
    content.classList.toggle('active');
    content.style.display = isActive ? 'none' : 'block';
}

// Function to toggle strategy accordion
function toggleStrategy(event) {
    const header = event.target.closest('.strategy-header');
    if (!header) {
        console.error("No strategy-header found for:", event.target);
        return;
    }
    const card = header.closest('.strategy-card');
    if (!card) {
        console.error("No strategy-card found for header:", header);
        return;
    }
    const content = card.querySelector('.strategy-content');
    if (!content) {
        console.error("No strategy-content found in card:", card);
        return;
    }

    console.log("Toggling strategy at:", new Date().toLocaleString('es-ES', { timeZone: 'CET' }), content);

    const isActive = content.classList.contains('active');
    content.classList.toggle('active');
    content.style.display = isActive ? 'none' : 'block';
}

// Function to prioritize a strategy
function prioritizeStrategy(concept, event) {
    event.stopPropagation(); // Prevent accordion toggle
    console.log("Prioritizing:", concept, "at:", new Date().toLocaleString('es-ES', { timeZone: 'CET' }));
    alert(`${concept} marked as high priority!`);
}

// Function to render chart (requires Chart.js)
function renderChart(config) {
    const ctx = document.getElementById('chartCanvas').getContext('2d');
    if (window.myChart) window.myChart.destroy();
    window.myChart = new Chart(ctx, config);
}

// Función para convertir Markdown **texto** a <strong>texto</strong>
function convertBold(text) {
    return text ? text.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>') : '';
}

document.addEventListener('DOMContentLoaded', () => {
    const form = document.getElementById('analysisForm');
    if (!form) {
        console.error('Elemento analysisForm no encontrado en el DOM. Verifica el ID en webpage.html.');
        return;
    }

    console.log('Form loaded at:', new Date().toLocaleString('es-ES', { timeZone: 'CET' }));

    form.addEventListener('submit', async (e) => {
        e.preventDefault();

        const formData = new FormData(form);
        const data = {
            location: formData.get('location') || 'Bogotá',
            candidate_name: formData.get('candidate_name') || '[Nombre del Candidato]'
        };

        console.log('Form data collected at:', new Date().toLocaleString('es-ES', { timeZone: 'CET' }), data);

        const resultsDiv = document.getElementById('results');
        resultsDiv.innerHTML = 'Procesando...';

        try {
            console.log('Sending fetch request to /analyze at:', new Date().toLocaleString('es-ES', { timeZone: 'CET' }));
            const response = await fetch('/analyze', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(data)
            });
            console.log('Fetch response received at:', new Date().toLocaleString('es-ES', { timeZone: 'CET' }), 'Status:', response.status);

            const result = await response.json();
            console.log('Parsed JSON from /analyze at:', new Date().toLocaleString('es-ES', { timeZone: 'CET' }), result);

            if (result.status === 'error') {
                resultsDiv.innerHTML = `Error: ${result.message || 'Error desconocido'}`;
                console.log('Error handled at:', new Date().toLocaleString('es-ES', { timeZone: 'CET' }), result.message);
                return;
            }

            // Store report data globally for tab switching
            window.currentReport = result.report || {};
            console.log('Report stored at:', new Date().toLocaleString('es-ES', { timeZone: 'CET' }), window.currentReport);

            // Initial render with the first tab active
            resultsDiv.innerHTML = `
                <div class="large-box">
                    <div class="tab-container">
                        <div class="tab active" data-section="resumen" onclick="switchTab(event)">Resumen Ejecutivo</div>
                        <div class="tab" data-section="analisis" onclick="switchTab(event)">Análisis de Datos</div>
                        <div class="tab" data-section="plan" onclick="switchTab(event)">Plan Estratégico</div>
                        <div class="tab" data-section="discurso" onclick="switchTab(event)">Discurso</div>
                        <div class="tab" data-section="grafico" onclick="switchTab(event)">Gráfico Sugerido</div>
                    </div>
                    <div id="content-area" class="content-area">
                        <h3>Análisis general de la situación política actual</h3>
                        <p>${convertBold(window.currentReport.resumen ? window.currentReport.resumen.replace(/^\s*-\s*/gm, '').replace('Tendencias generales', '<strong>Tendencias generales</strong>') : 'No hay resumen disponible')}</p>
                    </div>
                </div>
            `;

            console.log('DOM updated at:', new Date().toLocaleString('es-ES', { timeZone: 'CET' }));

        } catch (error) {
            console.error('Fetch or processing error at:', new Date().toLocaleString('es-ES', { timeZone: 'CET' }), error);
            resultsDiv.innerHTML = `Error: ${error.message}`;
        }
    });
});