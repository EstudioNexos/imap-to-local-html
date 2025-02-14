<div>
    {% if mails|length > 0 %}
    <table class="datatable table table-striped table-bordered">
        <thead>
            <tr>
                <th>Date</th>
                <th>From</th>
                <th>To</th>
                <th>Subject</th>
                <th>Size</th>
                <th></th>
            </tr>
        </thead>
        <tbody>
            {% for mail in mails %}
                <tr data-id="{{ mails[mail].id }}">
                    <td class="text-center"><span class="text-nowrap">{{ mails[mail].date }}</span></td>
                    <td>{{ mails[mail].from|simplify_emailheaders }}</td>
                    <td>{{ mails[mail].to|simplify_emailheaders }}</td>
                    <td>
                        {% if mails[mail].error_decoding %}
                            <i class="bi bi-exclamation-octagon btn-outline-danger" title="{{ mails[mail].error_decoding }}" />
                        {% endif %}
                        <a href="{{ link_prefix }}{{ mails[mail].link }}">{{ mails[mail].subject|e }}</a>
                    </td>
                    <td class="text-end" data-order="{{ mails[mail].size }}"><span class="text-nowrap">{{ mails[mail].size|humansize }}<span></td>
                    <td class="text-center">
                        {% if mails[mail].attachments %}
                            <i class="bi bi-paperclip" title="{{ mails[mail].attachments }} attachment(s)" />
                        {% endif %}
                    </td>
                </tr>
            {% else %}
                <tr><td colspan="7">Folder is empty</td></tr>
            {% endfor %}
        </tbody>
    </table>
    {% else %}
        <p class="alert alert-info">Folder is empty</p>
    {% endif %}
</div>