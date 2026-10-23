from pathlib import Path
import re
root = Path(".")
def edit(path, fn):
    p = root / path
    if p.exists():
        old = p.read_text()
        new = fn(old)
        if old != new:
            p.write_text(new)
            print("patched", path)
# Motion API compatibility
edit("lib/core/animations.dart", lambda s: s.replace(
    "static const Curve expressiveSpring = M3ESpringCurve(stiffness: 380, damping: 0.55);",
    "static const Curve expressiveSpring = Curves.easeOutBack;"
).replace(
    """    return M3ETappable(
      onTap: onTap,
      onLongPress: onLongPress,
      pressedScale: pressedScale,
      spring: M3EMotion.expressiveSpatialPress,
      enabled: enabled,
      child: child,
    );""",
    """    return GestureDetector(
      onTap: enabled ? onTap : null,
      onLongPress: enabled ? onLongPress : null,
      child: AnimatedScale(
        scale: 1.0,
        duration: const Duration(milliseconds: 180),
        curve: Curves.easeOutBack,
        child: child,
      ),
    );"""
).replace(
    """    originKey: originKey,
    duration: transitionDuration ?? const Duration(milliseconds: 420),
    reverseDuration: reverseTransitionDuration ?? const Duration(milliseconds: 340),
  );
}""",
    """    originKey: originKey,
  );
}"""
))
# Clamp returns num; Offset requires doubles.
edit("lib/widgets/effects/glass_container_transform.dart", lambda s: s.replace(
    "final clampedX = tapPos.dx.clamp(", "final clampedX = tapPos.dx.clamp("
).replace(
    "final clampedY = tapPos.dy.clamp(", "final clampedY = tapPos.dy.clamp("
).replace(
    "final clampedX = tapPos.dx.clamp(0.0, screenSize.width);",
    "final clampedX = tapPos.dx.clamp(0.0, screenSize.width).toDouble();"
).replace(
    "final clampedY = tapPos.dy.clamp(0.0, screenSize.height);",
    "final clampedY = tapPos.dy.clamp(0.0, screenSize.height).toDouble();"
))
# Correct theme variable in class card.
edit("lib/widgets/cards/class_card.dart", lambda s: s.replace("currentStyle", "themeStyle"))
# Deadline model exposes completion state used by the screen.
def deadlines(s):
    needle = """  const DeadlineData({
    required this.title,
    required this.date,
    required this.status,
  });
"""
    add = needle + """
  bool get isDone {
    final normalized = status.toLowerCase();
    if (normalized.contains('complete') || normalized == 'done' || normalized == 'passed') return true;
    if (normalized.contains('pending') || normalized.contains('upcoming')) return false;
    final parsed = DateTime.tryParse(date);
    return parsed != null && parsed.isBefore(DateTime.now());
  }
"""
    return s.replace(needle, add)
edit("lib/services/helpdesk_schedule_data_service.dart", deadlines)
# Convert nullable typed library schedule to the map shape used by the existing UI.
def library(s):
    return s.replace(
        "_libraryData = payload.librarySchedule;",
        """_libraryData = payload.librarySchedule == null
            ? const <String, dynamic>{}
            : <String, dynamic>{
                'open': payload.librarySchedule!.open,
                'break': payload.librarySchedule!.breakTime,
                'close': payload.librarySchedule!.close,
                'timings': <String>[
                  'Opening: ${payload.librarySchedule!.open}',
                  'Break: ${payload.librarySchedule!.breakTime}',
                  'Closing: ${payload.librarySchedule!.close}',
                ],
                'rules': const <String>[],
              };"""
    )
edit("lib/screens/tools/library_schedule_screen.dart", library)
# Resolve schedule info card imports.
for path in ["lib/screens/dashboard_screen.dart", "lib/screens/faculty/faculty_schedule_view.dart"]:
    def imp(s):
        line = "import 'package:iris/widgets/schedule_views/sports_gala_view.dart';"
        if line not in s:
            s = line + "\n" + s
        return s
    edit(path, imp)
# Use the callback's actual theme-style variable.
# Fix num->double casts where clamp values are fed to Offset.
# UniInfo uses a richer room record not present in core/models.dart; add a local adapter
# and map persisted rooms into it without claiming attendant details that aren't in Room.
def uni(s):
    s = s.replace("List<RoomData> _allRooms = [];", "List<_CampusRoomView> _allRooms = [];")
    s = s.replace("final allRooms = await roomSvc.loadRooms();", """final persistedRooms = await roomSvc.loadRooms();
    final allRooms = persistedRooms.map((r) {
      final details = RoomPersistenceService.detailsForRoom(r.id);
      return _CampusRoomView(
        id: r.id,
        building: r.building,
        floor: details?.floor ?? '',
        attendantName: details?.attendant,
        attendantContact: details?.mobile,
      );
    }).toList();""")
    if "class _CampusRoomView" not in s:
        s += """
\nclass _CampusRoomView {
  final String id;
  final String building;
  final String floor;
  final String? attendantName;
  final String? attendantContact;
  const _CampusRoomView({required this.id, required this.building, required this.floor, this.attendantName, this.attendantContact});
}
"""
    return s
edit("lib/screens/tools/uni_info_screen.dart", uni)
# Add a public lookup helper for the known room directory.
def room_service(s):
    marker = "  static const Map<String, RoomLocationDetails> _groundTruthRooms = {"
    # Add helper after map closing is structurally risky; instead expose a method before loadRooms.
    needle = "  static Future<List<Room>> loadRooms()"
    if needle in s and "detailsForRoom(" not in s:
        s = s.replace(needle, """  static RoomLocationDetails? detailsForRoom(String id) => _groundTruthRooms[id.toUpperCase()];

""" + needle)
    return s
edit("lib/services/room_persistence_service.dart", room_service)



# Follow-up repairs for diagnostics from the release compiler.
def compiler_fixes():
    p = Path("lib/widgets/effects/glass_container_transform.dart")
    if p.exists():
        s = p.read_text()
        s = re.sub(r"final clampedX = (tapPos\.dx\.clamp\([\s\S]*?\n      \));", r"final clampedX = (\1).toDouble()", s, count=1)
        s = re.sub(r"final clampedY = (tapPos\.dy\.clamp\([\s\S]*?\n      \));", r"final clampedY = (\1).toDouble()", s, count=1)
        # Preserve the assignment prefix after wrapping the clamp expression.
        s = s.replace("final clampedX = (", "final clampedX = (", 1)
        s = s.replace("final clampedY = (", "final clampedY = (", 1)
        p.write_text(s)

    p = Path("lib/widgets/controls/iris_expressive_controls.dart")
    if p.exists():
        s = p.read_text().replace(
            "segments: segments,\n                  height: height,",
            "segments: segments.map((segment) => lgw.GlassSegment(label: segment)).toList(),\n                  height: height,",
        )
        p.write_text(s)

    p = Path("lib/screens/faculty/faculty_schedule_view.dart")
    if p.exists():
        s = p.read_text()
        s = s.replace(
            "child: const Row(\n                      mainAxisSize: MainAxisSize.min,",
            "child: Row(\n                      mainAxisSize: MainAxisSize.min,",
        )
        p.write_text(s)

    p = Path("lib/services/room_persistence_service.dart")
    if p.exists() and "static RoomLocationDetails? detailsForRoom(" not in p.read_text():
        s = p.read_text()
        marker = "  static const String _key = 'iris_rooms';"
        s = s.replace(
            marker,
            marker + "\n\n  static RoomLocationDetails? detailsForRoom(String id) => _groundTruthRooms[id.toUpperCase()];",
        )
        p.write_text(s)

compiler_fixes()
