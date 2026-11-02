import 'package:flutter/material.dart';
import 'package:mind_ai/view/chatbot_screen.dart';
import 'package:mind_ai/view/dashboard_screen.dart';
import 'package:mind_ai/view/growth_screen.dart';
import 'package:mind_ai/view/learning_path_screen.dart';
import 'package:mind_ai/view/login_screen.dart';
import 'package:mind_ai/view/my_library_screen.dart';
import 'package:mind_ai/view/profile_screen.dart';
import 'package:mind_ai/view/quiz_screen.dart';
import 'package:mind_ai/view/register_screen.dart';
import 'package:mind_ai/view/welcome_screen.dart';

void main() {
  runApp(const MyApp());
}

class MyApp extends StatefulWidget {
  const MyApp({super.key});

  @override
  State<MyApp> createState() => _MyAppState();
}

class _MyAppState extends State<MyApp> {
  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      theme: ThemeData(
        fontFamily: 'PlusJakartaSans',
        useMaterial3: true,
        textTheme: const TextTheme(
          bodyLarge: TextStyle(fontWeight: FontWeight.w500),
          bodyMedium: TextStyle(fontWeight: FontWeight.w500),
          bodySmall: TextStyle(fontWeight: FontWeight.w400),
          titleLarge: TextStyle(fontWeight: FontWeight.w700),
          titleMedium: TextStyle(fontWeight: FontWeight.w600),
          titleSmall: TextStyle(fontWeight: FontWeight.w600),
        ),
      ),

      debugShowCheckedModeBanner: false,
      initialRoute: '/',
      routes: {
        '/': (context) => const WelcomeScreen(),
        '/login': (context) => const LoginScreen(),
        '/register': (context) => const RegisterScreen(),
        '/dashboard': (context) => const DashboardScreen(),
        '/profile': (context) => const ProfileScreen(),
        '/chatbot': (context) => const ChatbotScreen(),
        '/my-library': (context) => const MyLibraryScreen(),
        '/learning-path': (context) => const LearningPathScreen(),
        '/quiz': (context) => const QuizScreen(),
        '/growth': (context) => const GrowthScreen(),
      },
    );
  }
}
