class PdfModel {
  final int id;
  final String title;
  final String filename;
  final int fileSize;
  final int pageCount;
  final String uploadedAt;
  final int ownerId;

  PdfModel({
    required this.id,
    required this.title,
    required this.filename,
    required this.fileSize,
    required this.pageCount,
    required this.uploadedAt,
    required this.ownerId,
  });

  factory PdfModel.fromJson(Map<String, dynamic> json) {
    return PdfModel(
      id: (json['id'] as num).toInt(),
      title: json['title']?.toString() ?? '',
      filename: json['filename']?.toString() ?? '',
      fileSize: (json['file_size'] as num?)?.toInt() ?? 0,
      pageCount: (json['page_count'] as num?)?.toInt() ?? 0,
      uploadedAt: json['uploaded_at']?.toString() ?? '',
      ownerId: (json['owner_id'] as num?)?.toInt() ?? 0,
    );
  }
}
