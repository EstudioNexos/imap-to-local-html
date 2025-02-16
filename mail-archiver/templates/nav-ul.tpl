<ul class="nav flex-column">
    {% for item in menu %}
        <li class="nav-item">
            {% if item.selected %}
                {% if item.id == selected_folder or item.id in selected_folder %}
                    <a class="border rounded nav-link active text-primary" href="{{link_prefix}}{{ item.link }}" data-id="{{ item.id }}">
                        <span class="bi bi-folder2-open me-2 fs-4"></span>
                        {{ item.title }}
                    </a>
                {% else %}
                    <a class="border rounded nav-link" href="{{link_prefix}}{{ item.link }}" data-id="{{ item.id }}">
                        <span class="bi bi-folder2 me-2  fs-4"></span>
                        {{ item.title }}
                    </a>
                {% endif %}
            {% else %}
                <a class="border rounded nav-link not-selected" href="{{link_prefix}}{{ item.link }}" data-id="{{ item.id }}">
                    <span class="bi bi-folder2 me-2  fs-4"></span>
                    {{ item.title }}
                </a>
            {% endif %}
            {% if item.children %}
                {{ item.children }}
            {% endif %}
        </li>
    {% endfor %}
</ul>
