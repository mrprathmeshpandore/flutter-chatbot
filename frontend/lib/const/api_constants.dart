
class ApiConstants {
  static String get baseUrl {
    const configuredUrl = String.fromEnvironment('API_BASE_URL');

    if (configuredUrl.isNotEmpty) {
      return configuredUrl;
    }

    return 'https://flutter-chatbot-gqyx.onrender.com';
  }
}
