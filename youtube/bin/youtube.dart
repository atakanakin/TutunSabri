import 'dart:io';

import 'package:youtube/youtube.dart' as youtube;

Future<void> main(List<String> arguments) async {
  // arguments[2] is 'audio' if the user wants to download only the audio
  // it is 'video' if the user wants to download the full video
  // it is 'clip' if the user wants to download a clip of the video
  String path = await youtube.downloadVideo(
      arguments[0], arguments[1], arguments[2] == 'audio');
  if (arguments[2] == 'clip') {
    await youtube.extractClip(
        path,
        '${path.substring(0, path.length - 4)}_clip.mp4',
        arguments[3],
        arguments[4]);
    File(path).deleteSync();
    path = '${path.substring(0, path.length - 4)}_clip.mp4';
  }
  print(path);
}
