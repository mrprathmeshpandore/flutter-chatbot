import 'package:mind_ai/const/api_constants.dart';

class UserModel {
  final int id;
  final String email;
  final String? fullName;
  final String? phoneNumber;
  final String? profileImage;
  final bool isActive;
  final String? createdAt;

  UserModel({
    required this.id,
    required this.email,
    this.fullName,
    this.phoneNumber,
    this.profileImage,
    required this.isActive,
    this.createdAt,
  });

  factory UserModel.fromJson(Map<String, dynamic> json) {
    return UserModel(
      id: (json['id'] as num).toInt(),
      email: json['email']?.toString() ?? '',
      fullName: json['full_name']?.toString(),
      phoneNumber: json['phone_number']?.toString(),
      profileImage: json['profile_image']?.toString(),
      isActive: json['is_active'] as bool? ?? true,
      createdAt: json['created_at']?.toString(),
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'email': email,
      'full_name': fullName,
      'phone_number': phoneNumber,
      'profile_image': profileImage,
      'is_active': isActive,
      'created_at': createdAt,
    };
  }

  String? get avatarFullUrl {
    if (profileImage == null || profileImage!.trim().isEmpty) {
      return null;
    }
    final img = profileImage!.trim();
    if (img.startsWith('http://') || img.startsWith('https://')) {
      return img;
    }
    final base = ApiConstants.baseUrl.endsWith('/')
        ? ApiConstants.baseUrl.substring(0, ApiConstants.baseUrl.length - 1)
        : ApiConstants.baseUrl;
    final path = img.startsWith('/') ? img : '/$img';
    return '$base$path';
  }

  String get initials {
    if (fullName != null && fullName!.trim().isNotEmpty) {
      final parts = fullName!.trim().split(RegExp(r'\s+'));
      if (parts.length >= 2) {
        return '${parts[0][0]}${parts[1][0]}'.toUpperCase();
      }
      return parts[0][0].toUpperCase();
    }
    if (email.isNotEmpty) {
      return email[0].toUpperCase();
    }
    return 'U';
  }

  String get displayName {
    if (fullName != null && fullName!.trim().isNotEmpty) {
      return fullName!.trim();
    }
    if (email.contains('@')) {
      return email.split('@').first;
    }
    return email;
  }
}
