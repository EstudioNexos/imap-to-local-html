<ul class="folder-breadcrump">
    {% for folderTitle, folderLink in folderList %}
        <li>
            {% if folderLink %}
                <a href="{{ link_prefix }}{{ folderLink }}">{{ folderTitle }}</a>
            {% else %}
                {{ folderTitle }}
            {% endif %}
        </li>
    {% endfor %}
</ul>