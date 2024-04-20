import 'dart:io';

import 'package:youtube_explode_dart/youtube_explode_dart.dart';

Future<String> downloadVideo(String url, String path, bool onlyAudio) async {
  var youtubeService = YoutubeExplode();
  Video video;
  try {
    video = await youtubeService.videos.get(url);
  } catch (e) {
    throw Exception("Invalid URL or video not found.");
  }

  var finalPath = '$path/temp_content/${video.title}';
  var manifest =
      await youtubeService.videos.streamsClient.getManifest(video.id);

  var audioStream = manifest.audioOnly;
  var audioDown = audioStream.withHighestBitrate();
  var audioFile = youtubeService.videos.streamsClient.get(audioDown);
  await _saveVideo(audioFile, '$finalPath.mp3');
  if (onlyAudio) {
    return '$finalPath.mp3';
  }

  var videoStream = manifest.videoOnly;
  Set<String> qualities = videoStream.getAllVideoQualitiesLabel();
  int param = 0;
  for (var i = 0; i < qualities.length; i++) {
    if (qualities.elementAt(i).contains("1080p")) {
      param = i;
      break;
    }
  }

  var videoDown = videoStream.elementAt(param);
  var videoFile = youtubeService.videos.streamsClient.get(videoDown);
  await _saveVideo(videoFile, '${finalPath}_woaudio.mp4');
  youtubeService.close();
  int exitCode = await combineAudioVideo(
      '${finalPath}_woaudio.mp4', '$finalPath.mp3', finalPath);
  if (exitCode == 0) {
    File('${finalPath}_woaudio.mp4').deleteSync();
    File('$finalPath.mp3').deleteSync();
    return '$finalPath.mp4';
  } else {
    throw Exception(
        'An error occured while combining audio and video. Please try again.');
  }
}

Future _saveVideo(Stream<List<int>> videoFile, String savePath) async {
  final File file = File(savePath);
  await videoFile.pipe(file.openWrite());
}

Future<int> combineAudioVideo(String video, String audio, String path) async {
  var finalVideo = '$path.mp4';
  var ffmpeg = await Process.run('ffmpeg', [
    '-i',
    video,
    '-i',
    audio,
    '-c:v',
    'copy',
    '-c:a',
    'copy',
    '-y',
    finalVideo
  ]);
  int exitCode = ffmpeg.exitCode;
  return exitCode;
}

Future<void> extractClip(String inputVideo, String outputVideo,
    String startTime, String endTime) async {
  // TODO: Check for valid start and end times
  int startSecond = toSeconds(startTime);
  int endSecond = toSeconds(endTime);
  endTime = toMinutes(endSecond - startSecond);

  // Extract clip without re-encoding
  final result = await Process.run('ffmpeg', [
    '-ss',
    startTime,
    '-i',
    inputVideo,
    '-to',
    endTime,
    '-c',
    'copy',
    '-y',
    outputVideo
  ]);

  if (result.exitCode != 0) {
    throw Exception('Error extracting clip: ${result.stderr}');
  }
}

int toSeconds(String time) {
  var parts = time.split(':');
  return int.parse(parts[0]) * 60 + int.parse(parts[1]);
}

String toMinutes(int seconds) {
  var minutes = seconds ~/ 60;
  var remainingSeconds = seconds % 60;
  return '$minutes:${remainingSeconds.toString().padLeft(2, '0')}';
}
