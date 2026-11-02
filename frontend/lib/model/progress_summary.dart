import 'dart:convert';

ProgressSummary progressSummaryFromJson(String str) =>
    ProgressSummary.fromJson(json.decode(str));

String progressSummaryToJson(ProgressSummary data) =>
    json.encode(data.toJson());

int _toInt(dynamic value) {
  if (value == null) return 0;
  if (value is num) return value.toInt();
  return int.tryParse(value.toString()) ?? 0;
}

class ProgressSummary {
  final int totalPdfs;
  final int totalQuizzesTaken;
  final int averageQuizScore;
  final int learningPathsCount;
  final List<RecentActivity> recentActivity;

  ProgressSummary({
    required this.totalPdfs,
    required this.totalQuizzesTaken,
    required this.averageQuizScore,
    required this.learningPathsCount,
    required this.recentActivity,
  });

  factory ProgressSummary.fromJson(Map<String, dynamic> json) =>
      ProgressSummary(
        totalPdfs: _toInt(json['total_pdfs']),
        totalQuizzesTaken: _toInt(json['total_quizzes_taken']),
        averageQuizScore: _toInt(json['average_quiz_score']),
        learningPathsCount: _toInt(json['learning_paths_count']),
        recentActivity: (json['recent_activity'] as List? ?? [])
            .map((x) => RecentActivity.fromJson(x as Map<String, dynamic>))
            .toList(),
      );

  Map<String, dynamic> toJson() => {
    'total_pdfs': totalPdfs,
    'total_quizzes_taken': totalQuizzesTaken,
    'average_quiz_score': averageQuizScore,
    'learning_paths_count': learningPathsCount,
    'recent_activity': recentActivity.map((x) => x.toJson()).toList(),
  };
}

class RecentActivity {
  final String activityType;
  final String subject;
  final int? score;
  final String createdAt;

  RecentActivity({
    required this.activityType,
    required this.subject,
    required this.score,
    required this.createdAt,
  });

  factory RecentActivity.fromJson(Map<String, dynamic> json) => RecentActivity(
    activityType: json['activity_type']?.toString() ?? '',
    subject: json['subject']?.toString() ?? '',
    score: json['score'] == null ? null : _toInt(json['score']),
    createdAt: json['created_at']?.toString() ?? '',
  );

  Map<String, dynamic> toJson() => {
    'activity_type': activityType,
    'subject': subject,
    'score': score,
    'created_at': createdAt,
  };
}
