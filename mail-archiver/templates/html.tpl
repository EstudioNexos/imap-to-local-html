<!doctype html>
<html lang="en">
  <head>
    <!-- Required meta tags -->
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1, shrink-to-fit=no">

    <!-- Bootstrap CSS -->
    <link rel="stylesheet" href="{{link_prefix}}/{{assets_location}}bootstrap/bootstrap.min.css">
    <link rel="stylesheet" href="{{link_prefix}}/{{assets_location}}bootstrap-icons-1.11.3/font/bootstrap-icons.min.css">
    <link rel="stylesheet" href="{{link_prefix}}/{{assets_location}}css/dashboard.css">
    <link rel="stylesheet" href="{{link_prefix}}/{{assets_location}}datatables/datatables.min.css">

    <title>{{ title }}</title>
    <meta name="generator" content="Mail Archiver, https://github.com/xtsimpouris/imap-to-local-html">
  </head>
  <body>
    <nav class="navbar fixed-top bg-light flex-md-nowrap p-0 shadow">
        <a class="navbar-brand p-2" href="{{link_prefix}}/index.html">{{ username }}</a>
    </nav>
    <div class="row vh-100 mt-5">
        <nav class="col-md-3 vh-100 p-4 bg-light sidebar">
          <div class="sticky-top">
            {{ sidemenu }}
          </div>
        </nav>
    
        <main role="main" class="col-md-9 px-4">
          <div id="content" class="px-5">
            {{ header }}
            {{ content }}
          </div>
        </main>
    </div>

    <!-- Optional JavaScript -->
    <!-- jQuery first, then Popper.js, then Bootstrap JS -->
    <script src="{{link_prefix}}/{{assets_location}}jquery/jquery.min.js"></script>
    <script src="{{link_prefix}}/{{assets_location}}bootstrap/popper.min.js"></script>
    <script src="{{link_prefix}}/{{assets_location}}bootstrap/bootstrap.bundle.min.js"></script>
    <script src="{{link_prefix}}/{{assets_location}}datatables/datatables.min.js"></script>
    <script type="text/javascript">
      $(document).ready( function () {
        $('.datatable').DataTable();
      });
    </script>
  </body>
</html>
