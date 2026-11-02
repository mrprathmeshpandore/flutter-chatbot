import 'package:flutter/material.dart';

class BottomNavigation extends StatelessWidget {
  final int currentIndex;
  final ValueChanged<int> onTap;

  const BottomNavigation({
    super.key,
    required this.currentIndex,
    required this.onTap,
  });

  static const items = [
    (Icons.home_rounded, 'Home'),
    (Icons.menu_book_rounded, 'Library'),
    (Icons.route_rounded, 'Learn'),
    (Icons.bar_chart_rounded, 'Growth'),
  ];

  @override
  Widget build(BuildContext context) {
    return BottomNavigationBar(
      currentIndex: currentIndex,
      type: BottomNavigationBarType.fixed,
      selectedItemColor: const Color(0xFF5965E8),
      unselectedItemColor: const Color(0xFF85859A),
      onTap: onTap,
      items: items.map((item) {
        return BottomNavigationBarItem(icon: Icon(item.$1), label: item.$2);
      }).toList(),
    );
  }
}
