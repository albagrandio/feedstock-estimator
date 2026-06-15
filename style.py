from branca.element import Template, MacroElement

styles = {
    "nav": {
        "background-color": "#0B3F43",
        "justify-content": "flex-start",
        "height": "60px",
        "display": "flex",
        "align-items": "center",
        "font-family": "Lato",
    },
    "img": {
        "padding-left": "10px",
        "margin-right": "2px",
        "display": "block",
    },
    "span": {"color": "white", "padding": "1px", "font-weight": "bold", "font-size": "25px", "font-family": "Lato"},
    "active": {
        "color": "white",
        "background-color": "#0B3F43",
        "font-weight": "normal",
        "padding": "1px",
        "font-family": "Lato, sans-serif",
    },
}


class ToggleControl(MacroElement):
    def __init__(self):
        super().__init__()
        self._name = "ToggleControl"
        self.template = Template(
            """
        {% macro script(this, kwargs) %}
        var toggleControl = L.control({position: 'topright'});
        toggleControl.onAdd = function(map) {
            var div = L.DomUtil.create('div', 'toggle-control');
            div.innerHTML = '<select id="data-toggle"><option value="crops">Crops</option><option value="livestock">Livestock</option></select>';
            L.DomEvent.disableClickPropagation(div);
            return div;
        };
        toggleControl.addTo({{ this._parent.get_name() }});

        var dataToggle = document.getElementById('data-toggle');
        dataToggle.onchange = function() {
            var selectedValue = this.value;
            // Use Streamlit's setComponentValue to communicate with Python
            window.Streamlit.setComponentValue(selectedValue);
        }
        {% endmacro %}
        """
        )
