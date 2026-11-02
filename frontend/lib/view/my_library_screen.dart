
import 'package:flutter/material.dart';
import 'package:mind_ai/model/pdf_model.dart';
import 'package:mind_ai/repo/pdf_repo.dart';
import 'package:mind_ai/view/pdf_upload_screen.dart';
import 'package:mind_ai/view/pdf_viewer_screen.dart';

class MyLibraryScreen extends StatefulWidget {
  const MyLibraryScreen({super.key});

  @override
  State<MyLibraryScreen> createState() => _MyLibraryScreenState();
}

class _MyLibraryScreenState extends State<MyLibraryScreen> {
  late Future<List<PdfModel>> pdfFuture;

  String token = '';
  bool initialized = false;

  static const Color primary = Color(0xFF5965E8);

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();

    if (initialized) return;
    initialized = true;

    final args = ModalRoute.of(context)?.settings.arguments;

    if (args is String && args.isNotEmpty) {
      token = args;
      pdfFuture = PdfRepo().getPdfs(token: token);
    } else {
      pdfFuture = Future.error(
        Exception('Login token missing. Please log in again.'),
      );
    }
  }

  // Refresh PDF Library
  Future<void> refreshPdfs() async {
    setState(() {
      pdfFuture = PdfRepo().getPdfs(token: token);
    });

    await pdfFuture;
  }

  // Delete PDF Confirmation
  Future<void> _confirmDeletePdf(PdfModel pdf) async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (dialogContext) {
        return AlertDialog(
          backgroundColor: const Color(0xFFFBF9FF),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(20),
          ),
          title: const Text(
            'Delete PDF?',
            style: TextStyle(
              fontWeight: FontWeight.w800,
            ),
          ),
          content: Text(
            'Are you sure you want to delete "${pdf.title}"?\n\n'
            'This action cannot be undone.',
          ),
          actions: [
            TextButton(
              onPressed: () {
                Navigator.pop(dialogContext, false);
              },
              child: const Text('Cancel'),
            ),
            ElevatedButton(
              style: ElevatedButton.styleFrom(
                backgroundColor: Colors.red,
                foregroundColor: Colors.white,
              ),
              onPressed: () {
                Navigator.pop(dialogContext, true);
              },
              child: const Text('Delete'),
            ),
          ],
        );
      },
    );

    if (confirmed != true || !mounted) return;

    try {
      await PdfRepo().deletePdf(
        token: token,
        pdfId: pdf.id,
      );

      if (!mounted) return;

      await refreshPdfs();

      if (!mounted) return;

      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('PDF deleted successfully!'),
          backgroundColor: Colors.green,
        ),
      );
    } catch (e) {
      if (!mounted) return;

      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text('Could not delete PDF: $e'),
          backgroundColor: Colors.red,
        ),
      );
    }
  }

  // File Size Formatter
  String formatSize(int bytes) {
    if (bytes < 1024 * 1024) {
      return '${(bytes / 1024).toStringAsFixed(1)} KB';
    }

    return '${(bytes / (1024 * 1024)).toStringAsFixed(2)} MB';
  }

  // Date Formatter
  String formatDate(String value) {
    final date = DateTime.tryParse(value);

    if (date == null) return value;

    final d = date.toLocal();

    return '${d.day.toString().padLeft(2, '0')}/'
        '${d.month.toString().padLeft(2, '0')}/'
        '${d.year}';
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFFF8F7FF),

      appBar: AppBar(
        title: const Text(
          'My Library',
          style: TextStyle(
            color: Color(0xFF25252B),
            fontWeight: FontWeight.w800,
          ),
        ),
        backgroundColor: const Color(0xFFF8F7FF),
        elevation: 0,
        iconTheme: const IconThemeData(
          color: Color(0xFF25252B),
        ),
        actions: [
          IconButton(
            onPressed: () {
              refreshPdfs().catchError((_) {});
            },
            icon: const Icon(Icons.refresh_rounded),
            tooltip: 'Refresh PDFs',
          ),
        ],
      ),

      body: Container(
        decoration: const BoxDecoration(
          gradient: LinearGradient(
            begin: Alignment.topLeft,
            end: Alignment.bottomRight,
            colors: [
              Color(0xFFF1EFFF),
              Color(0xFFFBF9FF),
              Color(0xFFEFF8FF),
            ],
          ),
        ),

        child: SafeArea(
          child: Column(
            children: [
              Padding(
                padding: const EdgeInsets.fromLTRB(22, 18, 22, 18),
                child: Row(
                  children: [
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          const Text(
                            'Your documents',
                            style: TextStyle(
                              fontSize: 24,
                              fontWeight: FontWeight.w800,
                              color: Color(0xFF25252B),
                            ),
                          ),

                          const SizedBox(height: 6),

                          Text(
                            'All your uploaded PDFs in one place.',
                            style: TextStyle(
                              fontSize: 12,
                              color: Colors.grey.shade600,
                            ),
                          ),
                        ],
                      ),
                    ),

                    Container(
                      padding: const EdgeInsets.all(14),
                      decoration: BoxDecoration(
                        color: const Color(0xFFECEBFF),
                        borderRadius: BorderRadius.circular(17),
                      ),
                      child: const Icon(
                        Icons.library_books_rounded,
                        color: primary,
                        size: 27,
                      ),
                    ),
                  ],
                ),
              ),

              Expanded(
                child: FutureBuilder<List<PdfModel>>(
                  future: pdfFuture,
                  builder: (context, snapshot) {
                    if (snapshot.connectionState ==
                        ConnectionState.waiting) {
                      return const Center(
                        child: CircularProgressIndicator(
                          color: primary,
                        ),
                      );
                    }

                    if (snapshot.hasError) {
                      return _statusView(
                        icon: Icons.error_outline_rounded,
                        title: 'Could not load your PDFs',
                        subtitle: snapshot.error.toString(),
                        buttonText: 'Try again',
                        onPressed: () {
                          setState(() {
                            pdfFuture =
                                PdfRepo().getPdfs(token: token);
                          });
                        },
                      );
                    }

                    final pdfs = snapshot.data ?? [];

                    if (pdfs.isEmpty) {
                      return _statusView(
                        icon: Icons.folder_open_rounded,
                        title: 'Your library is empty',
                        subtitle: 'Upload your first PDF to get started.',
                        buttonText: 'Upload PDF',
                        onPressed: openUpload,
                      );
                    }

                    return RefreshIndicator(
                      color: primary,
                      onRefresh: refreshPdfs,
                      child: ListView(
                        padding: const EdgeInsets.fromLTRB(
                          20,
                          0,
                          20,
                          24,
                        ),
                        children: [
                          Container(
                            padding: const EdgeInsets.all(17),
                            margin: const EdgeInsets.only(bottom: 15),
                            decoration: BoxDecoration(
                              color: Colors.white.withValues(alpha: 0.9),
                              borderRadius: BorderRadius.circular(18),
                              border: Border.all(
                                color: const Color(0xFFEAE8F5),
                              ),
                            ),
                            child: Row(
                              children: [
                                const Icon(
                                  Icons.picture_as_pdf_rounded,
                                  color: primary,
                                  size: 25,
                                ),

                                const SizedBox(width: 12),

                                Expanded(
                                  child: Text(
                                    '${pdfs.length} PDF${pdfs.length == 1 ? '' : 's'} in your library',
                                    style: const TextStyle(
                                      fontWeight: FontWeight.w700,
                                      fontSize: 14,
                                      color: Color(0xFF25252B),
                                    ),
                                  ),
                                ),
                              ],
                            ),
                          ),

                          ...pdfs.map((pdf) => _pdfCard(pdf)),

                          const SizedBox(height: 12),

                          SizedBox(
                            height: 52,
                            child: ElevatedButton.icon(
                              onPressed: openUpload,
                              icon: const Icon(
                                Icons.cloud_upload_outlined,
                              ),
                              label: const Text('Upload another PDF'),
                              style: ElevatedButton.styleFrom(
                                backgroundColor: primary,
                                foregroundColor: Colors.white,
                                elevation: 0,
                                shape: RoundedRectangleBorder(
                                  borderRadius: BorderRadius.circular(15),
                                ),
                              ),
                            ),
                          ),
                        ],
                      ),
                    );
                  },
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  // PDF Card With Delete Icon
  Widget _pdfCard(PdfModel pdf) {
    return InkWell(
      borderRadius: BorderRadius.circular(20),

      onTap: () {
        debugPrint('PDF CARD TAPPED: ${pdf.id}');

        Navigator.push(
          context,
          MaterialPageRoute(
            builder: (_) => PdfViewerScreen(
              pdfId: pdf.id,
              title: pdf.title,
              token: token,
            ),
          ),
        );
      },

      child: Container(
        margin: const EdgeInsets.only(bottom: 13),
        padding: const EdgeInsets.all(16),

        decoration: BoxDecoration(
          color: Colors.white.withValues(alpha: 0.93),
          borderRadius: BorderRadius.circular(20),
          border: Border.all(
            color: const Color(0xFFEAE8F5),
          ),
        ),

        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Container(
              padding: const EdgeInsets.all(13),
              decoration: BoxDecoration(
                color: const Color(0xFFECEBFF),
                borderRadius: BorderRadius.circular(15),
              ),
              child: const Icon(
                Icons.picture_as_pdf_rounded,
                color: primary,
                size: 27,
              ),
            ),

            const SizedBox(width: 13),

            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    pdf.title,
                    style: const TextStyle(
                      fontSize: 14,
                      fontWeight: FontWeight.w800,
                      color: Color(0xFF25252B),
                    ),
                  ),

                  const SizedBox(height: 5),

                  Text(
                    pdf.filename,
                    maxLines: 2,
                    overflow: TextOverflow.ellipsis,
                    style: const TextStyle(
                      fontSize: 11,
                      color: Color(0xFF85859A),
                    ),
                  ),

                  const SizedBox(height: 10),

                  Wrap(
                    spacing: 12,
                    runSpacing: 5,
                    children: [
                      _metadata(
                        Icons.description_outlined,
                        '${pdf.pageCount} pages',
                      ),

                      _metadata(
                        Icons.storage_rounded,
                        formatSize(pdf.fileSize),
                      ),
                    ],
                  ),

                  const SizedBox(height: 7),

                  _metadata(
                    Icons.calendar_today_outlined,
                    formatDate(pdf.uploadedAt),
                  ),
                ],
              ),
            ),

            // DELETE BUTTON
            IconButton(
              onPressed: () => _confirmDeletePdf(pdf),
              icon: const Icon(
                Icons.delete_outline_rounded,
                color: Colors.redAccent,
                size: 23,
              ),
              tooltip: 'Delete PDF',
              constraints: const BoxConstraints(
                minWidth: 36,
                minHeight: 36,
              ),
              padding: EdgeInsets.zero,
            ),
          ],
        ),
      ),
    );
  }

  // PDF Metadata
  Widget _metadata(IconData icon, String text) {
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Icon(
          icon,
          size: 12,
          color: const Color(0xFF85859A),
        ),

        const SizedBox(width: 4),

        Text(
          text,
          style: const TextStyle(
            fontSize: 10,
            color: Color(0xFF85859A),
          ),
        ),
      ],
    );
  }

  // Empty / Error Screen
  Widget _statusView({
    required IconData icon,
    required String title,
    required String subtitle,
    required String buttonText,
    required VoidCallback onPressed,
  }) {
    return Center(
      child: SingleChildScrollView(
        padding: const EdgeInsets.all(28),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(
              icon,
              size: 52,
              color: primary,
            ),

            const SizedBox(height: 18),

            Text(
              title,
              textAlign: TextAlign.center,
              style: const TextStyle(
                fontSize: 19,
                fontWeight: FontWeight.w800,
                color: Color(0xFF25252B),
              ),
            ),

            const SizedBox(height: 9),

            Text(
              subtitle,
              textAlign: TextAlign.center,
              style: const TextStyle(
                fontSize: 12,
                height: 1.5,
                color: Color(0xFF85859A),
              ),
            ),

            const SizedBox(height: 20),

            ElevatedButton(
              onPressed: onPressed,
              style: ElevatedButton.styleFrom(
                backgroundColor: primary,
                foregroundColor: Colors.white,
              ),
              child: Text(buttonText),
            ),
          ],
        ),
      ),
    );
  }

  // Open PDF Upload Screen
  Future<void> openUpload() async {
    final result = await Navigator.push<bool>(
      context,
      MaterialPageRoute(
        builder: (_) => const PdfUploadScreen(),
        settings: RouteSettings(arguments: token),
      ),
    );

    if (result == true && mounted) {
      setState(() {
        pdfFuture = PdfRepo().getPdfs(token: token);
      });
    }
  }
}
