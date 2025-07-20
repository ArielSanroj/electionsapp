// Global variable to store the chart instance (will be removed)
let sentimentChart = null; // This will be irrelevant now

// Accordion toggle function
function toggleAccordion(event) {
    const header = event.target;
    const card = header.closest('.card');
    if (!card) {
        console.error("No parent card found for header:", header);
        return;
    }
    const content = card.querySelector('.accordion-content');
    if (!content) {
        console.error("No accordion-content element found in card:", card);
        return;
    }

    console.log("Toggling accordion, content element:", content, "Initial display:", content.style.display);

    const isActive = content.classList.contains('active');

    document.querySelectorAll('.accordion-content').forEach(item => {
        item.classList.remove('active');
        console.log("Closed accordion item:", item);
    });

    if (!isActive) {
        content.classList.add('active');
        console.log("Accordion content activated, innerHTML:", content.innerHTML, "New display:", content.style.display);
    }
}

// Función para convertir Markdown **texto** a <strong>texto</strong>
function convertBold(text) {
    return text.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
}

document.addEventListener('DOMContentLoaded', () => {
    const form = document.getElementById('analysisForm');
    if (!form) {
        console.error('Elemento analysisForm no encontrado en el DOM. Verifica el ID en webpage.html.');
        return;
    }

    form.addEventListener('submit', async (e) => {
        e.preventDefault();

        const formData = new FormData(e.target);
        const data = {
            location: formData.get('location'),
            candidate_name: formData.get('candidate_name')
        };

        const resultsDiv = document.getElementById('results');
        resultsDiv.innerHTML = 'Procesando...';

        try {
            const response = await fetch('/analyze', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(data)
            });
            const result = await response.json();

            if (result.status === 'error') {
                resultsDiv.innerHTML = `Error: ${result.message}`;
                return;
            }

            console.log("Received data from /analyze:", result.report);

            // Process and display results with bold conversion
            resultsDiv.innerHTML = `
                <h3>Resumen Ejecutivo</h3>
                <p>${convertBold(result.report.resumen.replace(/^\s*-\s*/gm, '').replace('Tendencias generales', '<strong>Tendencias generales</strong>'))}</p>
                <h3>Análisis de Datos</h3>
                <p>${convertBold(result.report.analisis.replace(/^\s*-\s*/gm, '').replace('Tendencias generales', '<strong>Tendencias generales</strong>'))}</p>
                <h3>Plan Estratégico</h3>
                <p>${convertBold(result.report.plan)}</p>
                <h3>Discurso</h3>
                <p>${convertBold(result.report.discurso)}</p>
                <h3>Gráfico Sugerido</h3>
                <p>${convertBold(result.report.grafico)}</p>
            `;

        } catch (error) {
            console.error("Fetch error:", error);
            resultsDiv.innerHTML = `Error: ${error.message}`;
        }
    });

    // Add event listeners to accordion headers after DOM is loaded
    document.querySelectorAll('.accordion-header').forEach(header => {
        header.addEventListener('click', toggleAccordion);
    });
});