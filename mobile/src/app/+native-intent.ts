export async function redirectSystemPath({
  path,
}: {
  path: string;
  initial: boolean;
}) {
  try {
    const incomingUrl = new URL(path);

    if (incomingUrl.hostname === 'expo-sharing') {
      return '/handle-share';
    }

    return path;
  } catch {
    return '/';
  }
}
