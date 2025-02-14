<ul class="nav flex-column">
    <li class="nav-item">
        {% for item in menu %}
            {% if item.selected %}
                {% if item.id == selected_folder or item.id in selected_folder %}
                    <a class="nav-link active" href="{{link_prefix}}{{ item.link }}" data-id="{{ item.id }}">
                        {{ item.title }}
                    </a>
                {% else %}
                    <a class="nav-link" href="{{link_prefix}}{{ item.link }}" data-id="{{ item.id }}">
                        {{ item.title }}
                    </a>
                {% endif %}
            {% else %}
                <a class="nav-link not-selected" href="{{link_prefix}}{{ item.link }}" data-id="{{ item.id }}">
                    {{ item.title }}
                </a>
            {% endif %}
            {% if item.children %}
                {{ item.children }}
            {% endif %}
        {% endfor %}
    </li>
</ul>
