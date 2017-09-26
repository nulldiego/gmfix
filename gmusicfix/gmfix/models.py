from django.db import models

# Create your models here.

from django.urls import reverse  # Used to generate URLs by reversing the URL patterns


class Track(models.Model):
    """
    Model representing a track
    """
    title = models.CharField(max_length=200)
    artist = models.CharField(max_length=200)
    album = models.CharField(max_length=200)
    google_id = models.CharField('Google ID', max_length=200)

    def __str__(self):
        """
        String for representing the Model object.
        """
        return self.artist + ' - ' + self.title


class Playlist(models.Model):
    """
    Model representing a Playlist
    """
    name = models.CharField(max_length=200)
    owner = models.CharField(max_length=200)
    google_id = models.CharField('Google ID', max_length=200)
    tracks = models.ManyToManyField(Track)

    def __str__(self):
        """
        String for representing the Model object.
        """
        return self.name

    def get_absolute_url(self):
        """
        Returns the url to access a particular book instance.
        """
        return reverse('playlist', args=[str(self.id)])